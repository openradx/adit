# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ADIT (Automated DICOM Transfer) is a Django web application for exchanging DICOM medical imaging data between PACS servers. It provides a web interface for managing transfers, batch operations, pseudonymization, and a REST API for programmatic access.

**Status**: Early beta (breaking changes anticipated)
**License**: AGPL 3.0 or later

## Essential Commands

All commands use `uv` package manager and run through `cli.py`:

```bash
# Development setup
uv sync                                    # Install dependencies
uv run cli init-workspace                  # Configure environment (creates .env)
uv run cli compose-up -- --watch           # Start dev containers with auto-reload
uv run cli compose-down                    # Stop containers

# Code quality (run on the host, no containers needed)
uv run cli lint                            # Run Ruff linter + pyright + djlint
uv run cli format-code                     # Format with Ruff (incl. import sort) + djlint --reformat

# Testing (pytest runs inside the web container, so dev containers must be up)
uv run cli test                            # Run all tests
uv run cli test -- --cov                   # Run tests with coverage
uv run cli test -- -k "test_name"          # Run specific test by name
uv run cli test -- adit/core/tests/        # Run tests in specific directory
uv run cli test -- -m acceptance           # Run acceptance tests only

# Database
uv run cli db-backup                       # Backup PostgreSQL
uv run cli db-restore                      # Restore PostgreSQL

# Utilities
uv run cli shell                           # Django shell in container
uv run cli populate-orthancs --reset       # Populate test DICOM servers (--reset clears them first)
uv run cli copy-statics                    # Sync JS libs to vendor folder

# Management commands (run inside the web container)
./manage.py populate_example_data          # Example DICOM servers, folders and jobs (dev boot)
./manage.py cleanup_jobs_and_tasks         # Mark stuck jobs/tasks FAILURE; interactive, workers idle
./manage.py receiver                       # Run the C-STORE SCP (what the receiver container does)
./manage.py sweep_stale_tasks              # Repair IN_PROGRESS tasks of dead workers (worker boot)
```

Example users and groups come from the shared `create_example_users` / `create_example_groups`
commands; the dev web container runs them plus `populate_example_data` at boot
(`docker-compose.dev.yml`). User docs live in `docs/` (MkDocs Material, `mkdocs.yml`; developer
docs in `docs/dev-docs/`).

## Architecture

### Tech Stack

Version floors are from `pyproject.toml`; the exact resolved version is in `uv.lock`.

- **Backend**: Python 3.12+ (images run 3.13), Django 6.1+ (locked 6.1), PostgreSQL 17
- **DICOM**: pynetdicom 2.1+ (locked 3.0), pydicom 2.4+ (locked 3.0), dicognito 0.17+ (anonymization)
- **Async**: Channels 4.2+ (locked 4.3), Daphne 4.1+ (locked 4.2) (ASGI/WebSockets)
- **Task Queue**: Procrastinate 3.0+ (locked 3.9) (PostgreSQL-backed)
- **Frontend**: Django templates, Cotton components, HTMX, Alpine.js, Bootstrap 5
- **API**: Django REST Framework 3.15+ (locked 3.18)

### Django Apps

- **core/**: Central job/task system, DICOM operations, shared models. Contains `DicomOperator`, `DimseConnector`, `DicomWebConnector` for PACS communication. Abstract bases: `DicomJob`, `DicomTask`, `TransferJob`, `TransferTask`, `DicomAppSettings` (the per-app `*Settings` models). Concrete models: `DicomNode`, `DicomServer`, `DicomFolder`, `DicomNodeGroupAccess`.
- **selective_transfer/**: Interactive study selection with WebSocket live updates. Uses Django Channels consumers for real-time progress. Models: `SelectiveTransferSettings`, `SelectiveTransferJob`, `SelectiveTransferTask`.
- **batch_query/**: Upload Excel spreadsheet to query DICOM servers, download results. Models: `BatchQuerySettings`, `BatchQueryJob`, `BatchQueryTask`, `BatchQueryResult`.
- **batch_transfer/**: Bulk transfer of studies between servers via Excel upload. Models: `BatchTransferSettings`, `BatchTransferJob`, `BatchTransferTask`.
- **mass_transfer/**: Bulk export of a date range from one server, partitioned (daily/weekly) into one task per partition. Series are discovered with JSON include/exclude filters (`FilterSpec`: modality, institution, study/series description, series number, age), optionally pseudonymized, and exported to a folder (converted to NIfTI) or to a server. Tasks run on the `mass_transfer` queue; `queue_mass_transfer_tasks` fans them out from the `default` queue. On the final attempt a failing series is logged and skipped instead of failing the partition. Models: `MassTransferSettings`, `MassTransferJob`, `MassTransferTask`, `MassTransferVolume`.
- **dicom_explorer/**: Browse DICOM servers and their studies/series interactively. Models: `DicomExplorerSettings`, `PermissionSupport`.
- **upload/**: Web portal for uploading DICOM files with client-side pseudonymization using dcmjs and dicom-web-anonymizer. Models: `UploadSettings`.
- **dicom_web/**: DICOMweb REST API endpoints - QIDO-RS (query), WADO-RS (retrieve, plus `.../nifti` endpoints that return studies/series/images converted to NIfTI), STOW-RS (store). Models: `DicomWebSettings`, `APIUsage`.

### Job/Task Processing Model

Transfer operations follow a Job -> Task pattern:

- A **TransferJob** contains multiple **TransferTasks**
- Tasks define: source server, destination node, study selection, pseudonymization options
- Status flow: `PENDING` -> `IN_PROGRESS` -> `SUCCESS`/`WARNING`/`FAILURE`
- Background workers (Procrastinate) poll and process tasks from three queues: `default`, `dicom` and `mass_transfer`
- Retries are two-level: Stamina retries each network call (`adit/core/utils/retry_config.py`, 5-10 attempts with exponential backoff, off via `ENABLE_STAMINA_RETRY=false`); Procrastinate retries the whole task on `RetriableDicomError` (`DICOM_TASK_MAX_ATTEMPTS=3`, linear wait 120 s + 120 s per retry, `adit/settings/base.py`)

### Job and Task Statuses

**Job statuses** (`DicomJob.Status`): `UNVERIFIED`, `PENDING`, `IN_PROGRESS`, `CANCELING`, `CANCELED`, `SUCCESS`, `WARNING`, `FAILURE`

**Task statuses** (`DicomTask.Status`): `PENDING`, `IN_PROGRESS`, `CANCELED`, `SUCCESS`, `WARNING`, `FAILURE`

The job status is derived from its tasks via `post_process()`. The evaluation priority is:
0. No tasks at all → job becomes SUCCESS with message "No tasks to process."
1. Any PENDING task → job becomes PENDING (unless job is CANCELING)
2. Any IN_PROGRESS task → job becomes IN_PROGRESS (unless job is CANCELING)
3. If job was `CANCELING` → job becomes `CANCELED`
4. Otherwise the job is finished and its final status is computed from the combination of `SUCCESS`, `WARNING`, and `FAILURE` tasks. If none of those are present but canceled tasks are, the job becomes `CANCELED`

### Worker Crash Recovery

Two layers hold the state of a running task and heal independently:

- **Queue rows** (`procrastinate_jobs`, `todo → doing → succeeded/failed`, deleted on finish). Healed by Procrastinate plus `retry_stalled_jobs` (web boot + every 10 min): a `doing` row whose worker heartbeat is older than 30 s goes back to `todo`.
- **Task rows** (`DicomTask`, `PENDING → IN_PROGRESS → …`). Only app code inside a running task moves them.

When a worker dies mid-task the task stays `IN_PROGRESS`. The stale task sweep (`adit/core/utils/recovery.py`) repairs it: every `IN_PROGRESS` task whose queue row is gone, finished, or owned by a worker silent for `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (default 30, never lower) is put back to `PENDING` (or `CANCELED` if the job is canceling) with one conditional UPDATE. If the old queue row will not run again the task is re-queued; otherwise the task keeps pointing at that row, so later sweeps recognize the run it starts. Each repair and each job re-evaluation (`post_process()`) is isolated: one failure is logged and the sweep continues, reporting one summary error at the end. It runs at every worker start (`./manage.py sweep_stale_tasks`, never exits non-zero) and periodically (`DICOM_TASK_SWEEP_CRON`, default every minute, `default` queue).

`_run_dicom_task` claims a task with a single `PENDING → IN_PROGRESS` UPDATE that also stamps the delivering queue row onto `queued_job`, and skips the delivery otherwise — Procrastinate delivers at least once, so a row may arrive for a task another run already handled.

Accepted: a worker frozen for more than the grace period but still alive can lead to the same task running twice (idempotent at the PACS, wasted work only); a task that repeatedly kills its worker is revived without a cap until canceled; `PENDING` tasks without a queue row are not repaired (use Restart/Reset); a task revived while its old queue row is still alive waits for `retry_stalled_jobs` to run that row again (up to 10 min); a job whose re-evaluation fails during a sweep keeps its stale status until a later action touches it.

### Job Actions

All job actions are defined in `adit/core/views.py`. Staff users can act on any job; regular users can only act on their own jobs.

| Action | Available when | Who can use | Effect on job | Effect on tasks |
|---|---|---|---|---|
| **Verify** | `UNVERIFIED` | Staff only | Sets job to `PENDING`, queues all pending tasks | Tasks are queued for processing |
| **Delete** | `UNVERIFIED` or `PENDING` (and no non-pending tasks) | Owner or staff | Queued Procrastinate jobs of its tasks are canceled and deleted, then the job is deleted | All tasks are deleted (cascade) |
| **Cancel** | `PENDING` or `IN_PROGRESS` | Owner or staff | Sets job to `CANCELED` (or `CANCELING` if tasks are in progress) | Pending tasks → `CANCELED` (queued jobs canceled). In-progress tasks are aborted via Procrastinate |
| **Resume** | `CANCELED` | Owner or staff | Sets job to `PENDING`, queues pending tasks | Canceled tasks → `PENDING`, then queued for processing |
| **Retry** | `FAILURE` | Owner or staff | Sets job to `PENDING`, queues pending tasks | Only failed tasks are reset via `reset_tasks()` (see Reset internals) and re-queued. Successful/warning tasks are left untouched |
| **Restart** | `CANCELED`, `SUCCESS`, `WARNING`, or `FAILURE` | Staff only | Sets job to `PENDING`, clears message, queues all tasks | All tasks are reset via `reset_tasks()` (see Reset internals) and re-queued |

### Task Actions

All task actions are defined in `adit/core/views.py`. Staff users can act on any task; regular users can only act on tasks belonging to their own jobs.

| Action | Available when | Who can use | Effect on task | Effect on job |
|---|---|---|---|---|
| **Delete** | `PENDING` | Owner or staff | Task is deleted | Job status is re-evaluated via `post_process()` |
| **Reset** | `CANCELED`, `SUCCESS`, `WARNING`, or `FAILURE` | Owner or staff | Task is reset to `PENDING` (attempts, message, log cleared), then re-queued | Job status is re-evaluated via `post_process()` — typically becomes `PENDING` |
| **Kill** | `IN_PROGRESS` | Staff only | Queued Procrastinate job is canceled with `abort=True, delete_job=True`: a `todo` row is deleted, a running `doing` row is flagged `abort_requested` and stays until the worker stops | Job status is not immediately changed; the task's processor sets it when it stops. If the worker is already dead, the stale task sweep repairs the task |

**Reset internals**: The `reset_tasks()` utility in `adit/core/utils/model_utils.py` clears the task back to its initial state: `status=PENDING`, `queued_job_id=None`, `attempts=0`, `message=""`, `log=""`, `start=None`, `end=None`. After resetting, the task is immediately re-queued via `queue_pending_task()` and the job status is re-evaluated via `post_process()`.

### DICOM Connectivity (`adit/core/utils/`)

High-level abstraction layers for PACS communication:

- **DicomOperator**: Main API for all DICOM operations
- **DimseConnector**: DIMSE protocol (C-FIND, C-GET, C-MOVE) via pynetdicom
- **DicomWebConnector**: DICOMweb REST API via dicomweb-client
- **FileTransmitClient**: Inter-container TCP file transfer for C-MOVE operations
- **StoreScp** (`store_scp.py`): C-STORE SCP server, run by `./manage.py receiver` in the receiver container
- **Pseudonymizer**: DICOM anonymization/pseudonymization using dicognito

Data modification pattern: download to temp folder -> transform (pseudonymize) -> upload to destination

### Docker Services

- **init**: One-shot bootstrap in production: `migrate`, `collectstatic`, `create_superuser`, `retry_stalled_jobs`, then an `ok_server` the web replicas wait for. In dev it is behind `profiles: [never]`; the web container runs the bootstrap itself
- **web**: Main application. Dev: Django dev server on `WEB_DEV_PORT` (8000), boots with `migrate`, superuser/example users/groups/data, `populate_orthancs`, `retry_stalled_jobs`. Prod: Daphne on 80/443, `WEB_REPLICAS` replicas
- **default_worker**: General background task processor (Procrastinate queue: `default`); each worker runs `sweep_stale_tasks` before `bg_worker`
- **dicom_worker**: DICOM-specific task processor (Procrastinate queue: `dicom`); each worker runs `sweep_stale_tasks` before `bg_worker`
- **mass_transfer_worker**: Mass transfer task processor (Procrastinate queue: `mass_transfer`); each worker runs `sweep_stale_tasks` before `bg_worker`
- **receiver**: C-STORE SCP server (port 11112 internal; 11122 on host in dev, `RECEIVER_PORT` in prod) - receives DICOM from C-MOVE
- **postgres**: PostgreSQL 17 database (port 5432, published on the host only in dev via `POSTGRES_DEV_PORT`)
- **orthanc1**: Test DICOM server (DICOM port 7501, published on host; HTTP 6501 internal, admin proxy at `/orthanc1/`)
- **orthanc2**: Test DICOM server (DICOM port 7502, published on host; HTTP 6502 internal, admin proxy at `/orthanc2/`)

## Environment Variables

Key variables in `.env` (see `example.env`, the source of truth for meaning). Values must not be
quoted: the file is passed to the containers as is, and `docker stack deploy` keeps the quotes.

- `ENVIRONMENT`: `development` or `production`
- `DJANGO_SECRET_KEY`: Cryptographic signing key
- `POSTGRES_PASSWORD`: Database password (production only)
- `DJANGO_ALLOWED_HOSTS`: Comma-separated allowed hosts (also `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_INTERNAL_IPS`)
- `TOKEN_AUTHENTICATION_SALT`: Salt for hashing API tokens (changing it invalidates all existing tokens)
- `SITE_NAME`, `SITE_DOMAIN`: Synced to the Django sites framework
- `DJANGO_SERVER_EMAIL`, `DJANGO_EMAIL_URL`, `DJANGO_ADMIN_EMAIL`, `DJANGO_ADMIN_FULL_NAME`, `SUPPORT_EMAIL`: Sender, SMTP URL (production only; dev logs mails to the console), error/approval recipient, support contact
- `SUPERUSER_USERNAME`, `SUPERUSER_EMAIL`, `SUPERUSER_PASSWORD`, `SUPERUSER_AUTH_TOKEN`: Superuser created by `create_superuser`
- `BACKUP_DIR`, `BACKUP_ENABLED`, `BACKUP_CRON`: Backup folder, on/off and schedule of the `backup_db` periodic task (default `0 3 * * *`)
- `WAIT_POSTGRES_TIMEOUT`: Seconds containers wait for Postgres at startup (default 180)
- `WEB_REPLICAS`, `DICOM_WORKER_REPLICAS`, `MASS_TRANSFER_WORKER_REPLICAS`: Service scaling (production)
- `ADIT_IMAGE`, `STACK_NAME`: Image for the app services and Swarm stack name (default `adit_dev` / `adit_prod`; also derives session/CSRF cookie names)
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OTLP HTTP endpoint for OpenTelemetry
- `TIME_ZONE`: Server timezone (default `UTC`)
- `CALLING_AE_TITLE`: ADIT's DICOM Application Entity title (required; `example.env` uses `ADIT1DEV`)
- `RECEIVER_AE_TITLE`: C-STORE receiver AE title (required; `example.env` uses `ADIT1DEV`)
- `EXCLUDE_MODALITIES`: Modalities skipped when a study is transferred or downloaded pseudonymized via the web UI; does not affect the client (default empty; `example.env` sets `PR,SR`)
- `ANONYMIZATION_SEED`: Seed for client-side anonymization consistency
- `MOUNT_DIR`: Directory for mounting download folders
- `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS`: Seconds without worker heartbeat before an `IN_PROGRESS` task counts as abandoned (default 30, never lower)
- `DICOM_TASK_SWEEP_CRON`: Schedule of the stale task sweep (default `* * * * *`)

## Code Standards

- **Style Guide**: Google Python Style Guide
- **Line Length**: 100 characters (Ruff), 120 for templates (djlint)
- **Type Checking**: pyright in basic mode (migrations and notebooks ignored, `reportUnnecessaryTypeIgnoreComment` on)
- **Linting**: Ruff with E, F, I, DJ, UP rules
- **Pre-commit**: `.pre-commit-config.yaml` (`uv run pre-commit install`) runs the same ruff, djlint and
  pyright checks as `uv run cli lint` plus `uv lock --check` (root and `adit-client`) and generic file hooks
- **Comments**: only where the code cannot speak for itself; explain *why*, not *what*
- **No history in comments**: describe the code as it is, not how it changed — that
  belongs in the commit message (docstrings too)
- **Keep the docs in sync**: when a change adds a feature or alters behaviour that the docs
  describe (README.md, docs/, this file, in-app help templates such as
  `adit/*/templates/*/_*_help.html`), update them in the same PR

### Assertions

- Use `assert` for internal programming error checks (preconditions, invariants). Do not replace with `ValueError` or similar — this app is never run with `python -O`.

### Django Field Conventions

- Text/char fields: use `blank=True` alone (not `null=True`)
- Non-string fields: use both `blank=True` and `null=True`
- String fields with no initial value: use `default=""`

## Key Dependencies

- **adit-radis-shared**: Shared infrastructure (accounts, token auth, CLI commands, UI components)
- **adit-client/**: Official Python client library for API access (included in repo)
- **dicognito**: DICOM pseudonymization/anonymization
- **procrastinate**: PostgreSQL-backed task queue
- **channels/daphne**: WebSocket support for real-time UI
- **pynetdicom**: DIMSE protocol implementation
- **dicomweb-client**: DICOMweb REST API client

## Testing

- **Framework**: pytest with pytest-django, pytest-asyncio
- **Acceptance tests**: pytest-playwright (Chromium), marked with `@pytest.mark.acceptance`
- **Test locations**: `adit/*/tests/`, `adit-client/**/tests/`
- **Factories**: factory-boy for test data generation
- **Helpers**: `adit/core/utils/testing_helpers.py` for DICOM test utilities

## API Examples

`adit-client` wraps ADIT's DICOMweb API (QIDO-RS, WADO-RS, STOW-RS plus the NIfTI retrieve
endpoints); servers are addressed by AE title. It cannot create or manage transfer jobs.
Signatures: `adit-client/adit_client/client.py`.

```python
from adit_client import AditClient

client = AditClient(server_url="https://adit.example.com", auth_token="your-token")

# QIDO-RS: query studies on the server with AE title PACS1
studies = client.search_for_studies(
    "PACS1", {"PatientID": "12345", "StudyDate": "20240101-20241231"}
)

# WADO-RS: retrieve all instances of a study, optionally pseudonymized
instances = client.retrieve_study("PACS1", studies[0].StudyInstanceUID, pseudonym="ABC123")

# STOW-RS: store instances on another server
client.store_images("PACS2", instances)

# NIfTI: (filename, BytesIO) tuples of the converted series
nifti_files = client.retrieve_nifti_series("PACS1", study_uid="1.2.3", series_uid="1.2.3.4")
```

## Troubleshooting

Plain `docker compose` does not find the project; it needs the compose files and project name
the CLI uses (prod: `docker-compose.prod.yml`, `-p adit_prod`; `STACK_NAME` overrides the name):

```bash
COMPOSE="docker compose -f docker-compose.base.yml -f docker-compose.dev.yml -p adit_dev"
```

### DICOM Connectivity Issues

- Verify AE titles match in both ADIT and PACS configuration
- Check firewall rules for DICOM ports (typically 104, 11112)
- Use `uv run cli populate-orthancs --reset` to reset test servers (without `--reset` it only adds)

### Worker Not Processing Tasks

- Check worker logs: `$COMPOSE logs dicom_worker`
- Verify the workers are running: `$COMPOSE ps`
- Check PostgreSQL connection in worker container

### C-STORE Failures

- Ensure receiver container is running: `$COMPOSE ps receiver`
- Verify `RECEIVER_AE_TITLE` matches PACS configuration
- Check receiver logs: `$COMPOSE logs receiver`

### WebSocket Updates Not Working

- `daphne` is in `INSTALLED_APPS`, so `runserver` serves ASGI in dev; prod runs Daphne directly
- Check browser console for WebSocket connection errors
- Verify the routing in `adit/asgi.py` (`selective_transfer/routing.py`) and that the page's host is in `DJANGO_ALLOWED_HOSTS`; `AllowedHostsOriginValidator` rejects other origins
