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

# Code quality
uv run cli lint                            # Run Ruff linter + pyright + djlint
uv run cli format-code                     # Format code with Ruff

# Testing
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
./manage.py populate_orthancs --reset      # Populate test DICOM servers
./manage.py populate_example_data          # Setup example users and DICOM servers
uv run cli copy_statics                    # Sync JS libs to vendor folder
```

## Architecture

### Tech Stack

- **Backend**: Python 3.12+, Django 5.1, PostgreSQL 17
- **DICOM**: pynetdicom 2.1.1, pydicom 2.4.4, dicognito (anonymization)
- **Async**: Channels 4.2.0, Daphne 4.1.2 (ASGI/WebSockets)
- **Task Queue**: Procrastinate 3.0.2 (PostgreSQL-backed)
- **Frontend**: Django templates, Cotton components, HTMX, Alpine.js, Bootstrap 5
- **API**: Django REST Framework 3.15.2

### Django Apps

- **core/**: Central job/task system, DICOM operations, shared models. Contains `DicomOperator`, `DimseConnector`, `DicomWebConnector` for PACS communication. Models: `DicomNode`, `DicomServer`, `DicomFolder`, `TransferJob`, `TransferTask`.
- **selective_transfer/**: Interactive study selection with WebSocket live updates. Uses Django Channels consumers for real-time progress. Models: `SelectiveTransferJob`, `SelectiveTransferTask`.
- **batch_query/**: Upload Excel spreadsheet to query DICOM servers, download results. Models: `BatchQueryJob`, `BatchQueryTask`, `BatchQueryResult`.
- **batch_transfer/**: Bulk transfer of studies between servers via Excel upload. Models: `BatchTransferJob`, `BatchTransferTask`.
- **dicom_explorer/**: Browse DICOM servers and their studies/series interactively. Models: `DicomExplorerSettings`.
- **upload/**: Web portal for uploading DICOM files with client-side pseudonymization using dcmjs and dicom-web-anonymizer. Models: `UploadSettings`.
- **dicom_web/**: DICOMweb REST API endpoints - QIDO-RS (query), WADO-RS (retrieve), STOW-RS (store).

### Job/Task Processing Model

Transfer operations follow a Job -> Task pattern:

- A **TransferJob** contains multiple **TransferTasks**
- Tasks define: source server, destination node, study selection, pseudonymization options
- Status flow: `PENDING` -> `IN_PROGRESS` -> `SUCCESS`/`WARNING`/`FAILURE`
- Background workers (Procrastinate) poll and process tasks from three queues: `default`, `dicom` and `mass_transfer`

### Job and Task Statuses

**Job statuses** (`DicomJob.Status`): `UNVERIFIED`, `PENDING`, `IN_PROGRESS`, `CANCELING`, `CANCELED`, `SUCCESS`, `WARNING`, `FAILURE`

**Task statuses** (`DicomTask.Status`): `PENDING`, `IN_PROGRESS`, `CANCELED`, `SUCCESS`, `WARNING`, `FAILURE`

The job status is derived from its tasks via `post_process()`. The evaluation priority is:
1. Any PENDING task → job becomes PENDING (unless job is CANCELING)
2. Any IN_PROGRESS task → job becomes IN_PROGRESS (unless job is CANCELING)
3. If job was `CANCELING` → job becomes `CANCELED`
4. Otherwise the job is finished and its final status is computed from the combination of `SUCCESS`, `WARNING`, and `FAILURE` tasks. If none of those are present but canceled tasks are, the job becomes `CANCELED`

### Worker Crash Recovery

Two layers hold the state of a running task and heal independently:

- **Queue rows** (`procrastinate_jobs`, `todo → doing → succeeded/failed`, deleted on finish). Healed by Procrastinate plus `retry_stalled_jobs` (web boot + every 10 min): a `doing` row whose worker heartbeat is older than 30 s goes back to `todo`.
- **Task rows** (`DicomTask`, `PENDING → IN_PROGRESS → …`). Only app code inside a running task moves them.

When a worker dies mid-task the task stays `IN_PROGRESS`. The stale task sweep (`adit/core/utils/recovery.py`) repairs it: every `IN_PROGRESS` task whose queue row is gone, finished, or owned by a worker silent for `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (default 30, never lower) is put back to `PENDING` (or `CANCELED` if the job is canceling) with one conditional UPDATE and re-queued if its old row will not run again; affected jobs are re-evaluated with `post_process()`. It runs at every worker start (`./manage.py sweep_stale_tasks`, never exits non-zero) and periodically (`DICOM_TASK_SWEEP_CRON`, default every minute, `default` queue).

`_run_dicom_task` claims a task with a single `PENDING → IN_PROGRESS` UPDATE and skips the delivery otherwise — Procrastinate delivers at least once, so a row may arrive for a task another run already handled.

Accepted: a worker frozen for more than the grace period but still alive can lead to the same task running twice (idempotent at the PACS, wasted work only); a task that repeatedly kills its worker is revived without a cap until canceled; `PENDING` tasks without a queue row are not repaired (use Restart/Reset).

### Job Actions

All job actions are defined in `adit/core/views.py`. Staff users can act on any job; regular users can only act on their own jobs.

| Action | Available when | Who can use | Effect on job | Effect on tasks |
|---|---|---|---|---|
| **Verify** | `UNVERIFIED` | Staff only | Sets job to `PENDING`, queues all pending tasks | Tasks are queued for processing |
| **Delete** | `UNVERIFIED` or `PENDING` (and no non-pending tasks) | Owner or staff | Job is deleted | All tasks are deleted (cascade) |
| **Cancel** | `PENDING` or `IN_PROGRESS` | Owner or staff | Sets job to `CANCELED` (or `CANCELING` if tasks are in progress) | Pending tasks → `CANCELED` (queued jobs canceled). In-progress tasks are aborted via Procrastinate |
| **Resume** | `CANCELED` | Owner or staff | Sets job to `PENDING`, queues pending tasks | Canceled tasks → `PENDING`, then queued for processing |
| **Retry** | `FAILURE` | Owner or staff | Sets job to `PENDING`, queues pending tasks | Only failed tasks are reset (`PENDING`, attempts/message/log cleared) and re-queued. Successful/warning tasks are left untouched |
| **Restart** | `CANCELED`, `SUCCESS`, `WARNING`, or `FAILURE` | Staff only | Sets job to `PENDING`, clears message, queues all tasks | All tasks are reset (`PENDING`, attempts/message/log cleared) and re-queued |

### Task Actions

All task actions are defined in `adit/core/views.py`. Staff users can act on any task; regular users can only act on tasks belonging to their own jobs.

| Action | Available when | Who can use | Effect on task | Effect on job |
|---|---|---|---|---|
| **Delete** | `PENDING` | Owner or staff | Task is deleted | Job status is re-evaluated via `post_process()` |
| **Reset** | `CANCELED`, `SUCCESS`, `WARNING`, or `FAILURE` | Owner or staff | Task is reset to `PENDING` (attempts, message, log cleared), then re-queued | Job status is re-evaluated via `post_process()` — typically becomes `PENDING` |
| **Kill** | `IN_PROGRESS` | Staff only | Queued Procrastinate job is asked to abort (the row itself is not deleted while running) | Job status is not immediately changed; the task's processor sets it when it stops. If the worker is already dead, the stale task sweep repairs the task |

**Reset internals**: The `reset_tasks()` utility in `adit/core/utils/model_utils.py` clears the task back to its initial state: `status=PENDING`, `queued_job_id=None`, `attempts=0`, `message=""`, `log=""`, `start=None`, `end=None`. After resetting, the task is immediately re-queued via `queue_pending_task()` and the job status is re-evaluated via `post_process()`.

### DICOM Connectivity (`adit/core/utils/`)

High-level abstraction layers for PACS communication:

- **DicomOperator**: Main API for all DICOM operations
- **DimseConnector**: DIMSE protocol (C-FIND, C-GET, C-MOVE) via pynetdicom
- **DicomWebConnector**: DICOMweb REST API via dicomweb-client
- **FileTransmitClient**: Inter-container TCP file transfer for C-MOVE operations
- **Receiver**: Separate container running C-STORE SCP server
- **Pseudonymizer**: DICOM anonymization/pseudonymization using dicognito

Data modification pattern: download to temp folder -> transform (pseudonymize) -> upload to destination

### Docker Services

- **web**: Django dev server (port 8000) - main application
- **default_worker**: General background task processor (Procrastinate queue: `default`); each worker runs `sweep_stale_tasks` before `bg_worker`
- **dicom_worker**: DICOM-specific task processor (Procrastinate queue: `dicom`); each worker runs `sweep_stale_tasks` before `bg_worker`
- **mass_transfer_worker**: Mass transfer task processor (Procrastinate queue: `mass_transfer`)
- **receiver**: C-STORE SCP server (port 11112 internal, 11122 on host) - receives DICOM from C-MOVE
- **postgres**: PostgreSQL 17 database (port 5432)
- **orthanc1**: Test DICOM server (ports 4242 DICOM, 7501 web)
- **orthanc2**: Test DICOM server (ports 4243 DICOM, 7502 web)

## Environment Variables

Key variables in `.env` (see `example.env`):

- `ENVIRONMENT`: `development` or `production`
- `DJANGO_SECRET_KEY`: Cryptographic signing key
- `POSTGRES_PASSWORD`: Database password
- `DJANGO_ALLOWED_HOSTS`: Comma-separated allowed hosts
- `CALLING_AE_TITLE`: ADIT's DICOM Application Entity title (default: ADIT)
- `RECEIVER_AE_TITLE`: C-STORE receiver AE title (default: ADIT_RECEIVER)
- `EXCLUDE_MODALITIES`: Modalities to skip in pseudonymization (default: PR,SR)
- `ANONYMIZATION_SEED`: Seed for client-side anonymization consistency
- `MOUNT_DIR`: Directory for mounting download folders
- `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS`: Seconds without worker heartbeat before an `IN_PROGRESS` task counts as abandoned (default 30, never lower)
- `DICOM_TASK_SWEEP_CRON`: Schedule of the stale task sweep (default `* * * * *`)

## Code Standards

- **Style Guide**: Google Python Style Guide
- **Line Length**: 100 characters (Ruff), 120 for templates (djlint)
- **Type Checking**: pyright in basic mode (migrations excluded)
- **Linting**: Ruff with E, F, I, DJ rules
- **Comments**: only where the code cannot speak for itself; explain *why*, not *what*
- **No history in comments**: describe the code as it is, not how it changed — that
  belongs in the commit message (docstrings too)

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

Using `adit-client` for programmatic access:

```python
from adit_client import AditClient

# Initialize client
client = AditClient(server_url="https://adit.example.com", auth_token="your-token")

# Query studies from a DICOM server
results = client.query_studies(
    source_server="PACS1",
    patient_id="12345",
    study_date="20240101-20241231"
)

# Create a transfer job
job = client.create_transfer_job(
    source_server="PACS1",
    destination_server="PACS2",
    study_uids=["1.2.3.4.5"],
    pseudonymize=True
)
```

## Troubleshooting

### DICOM Connectivity Issues

- Verify AE titles match in both ADIT and PACS configuration
- Check firewall rules for DICOM ports (typically 104, 11112)
- Use `./manage.py populate_orthancs` to reset test servers

### Worker Not Processing Tasks

- Check worker logs: `docker compose logs dicom_worker`
- Verify Procrastinate is running: `docker compose ps`
- Check PostgreSQL connection in worker container

### C-STORE Failures

- Ensure receiver container is running: `docker compose ps receiver`
- Verify `RECEIVER_AE_TITLE` matches PACS configuration
- Check receiver logs: `docker compose logs receiver`

### WebSocket Updates Not Working

- Ensure Daphne is running (not Django dev server alone)
- Check browser console for WebSocket connection errors
- Verify Channels layer is configured in settings
