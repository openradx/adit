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
- Background workers (Procrastinate) poll and process tasks from two queues: `default` and `dicom`

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
- **default_worker**: General background task processor (Procrastinate queue: `default`)
- **dicom_worker**: DICOM-specific task processor (Procrastinate queue: `dicom`)
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

## Code Standards

- **Style Guide**: Google Python Style Guide
- **Line Length**: 100 characters (Ruff), 120 for templates (djlint)
- **Type Checking**: pyright in basic mode (migrations excluded)
- **Linting**: Ruff with E, F, I, DJ rules

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
