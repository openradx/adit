# **ADIT Architecture Documentation**

This document provides a comprehensive overview of ADIT's architecture, implementation details, and key components for developers.

## System Overview

ADIT (Automated DICOM Transfer) is a full-stack web application designed for automated DICOM transfers. The system consists of a Django-based backend, PostgreSQL database, and server-side rendered web interface enhanced with HTMX for dynamic interactions.

ADIT inherits common functionality from **[ADIT Radis Shared](https://github.com/openradx/adit-radis-shared)**, a shared library that provides core components including user authentication, token-based authentication, common utilities, and shared Django applications used by both ADIT and RADIS projects.

## High-Level Architecture

The ADIT platform provides automated DICOM retrieval, transformation, and transfer through coordinated Docker containers. Users access the system via **web browser** or **ADIT Client** (Python library for programmatic access), performing operations such as creating transfer jobs, uploading DICOM files, and configuring destinations.

The system consists of three main components: a Django API server handling web UI and orchestration, a PostgreSQL database storing all persistent data and serving as the task queue, and transfer workers executing DICOM operations in the background.

## Backend Architecture

**Django Web/API Server**: Central coordination engine providing REST API endpoints, authentication, user/session management, static assets, and task orchestration. Creates job/task records in PostgreSQL and schedules background work.

**PostgreSQL Database**: System of record storing user accounts, transfer jobs, DICOM node configuration, task queue entries, execution history, and study metadata.

**Transfer Workers**: Docker containers polling PostgreSQL for tasks, executing C-GET/C-MOVE/DICOMweb operations, applying pseudonymization, and logging results.

### Procrastinate Task Queue System

ADIT uses [Procrastinate](https://procrastinate.readthedocs.io/en/stable/), a PostgreSQL-based task queue storing jobs directly in the database without external message brokers. Tasks are Python functions with decorators, supporting job scheduling, prioritization, retry logic, cancellation, and periodic (cron) tasks. Workers scale horizontally with configurable concurrency, graceful shutdown, and health monitoring.

**Tasks** (`adit/core/tasks.py`, `adit/mass_transfer/tasks.py`): `process_dicom_task` (`dicom` queue), `process_mass_transfer_task` (`mass_transfer` queue), `queue_mass_transfer_tasks` and `check_disk_space` (`default` queue), `sweep_stale_tasks_periodic` (see below). `backup_db`, `retry_stalled_jobs` and `broadcast_mail` come from `adit_radis_shared`.

Tasks run in a separate process with a timeout (`DICOM_TASK_PROCESS_TIMEOUT`, 20 minutes; `MASS_TRANSFER_PROCESS_TIMEOUT` for mass transfers). A `RetriableDicomError` retries the task up to `DICOM_TASK_MAX_ATTEMPTS` (3) times with linear backoff (2 → 4 → 6 minutes); transient network errors are retried first at the connector level by [stamina](https://stamina.hynek.me/).

#### Task recovery

A worker claims a task with one conditional `PENDING → IN_PROGRESS` UPDATE that records the Procrastinate row in `DicomTask.queued_job`, so a duplicate delivery is skipped. If the worker dies, the task stays `IN_PROGRESS` until the stale task sweep (`adit/core/utils/recovery.py`) puts it back to `PENDING` (or `CANCELED` for a canceling job) and re-queues it. The sweep catches every `IN_PROGRESS` task whose queue row is gone, finished, or whose worker sent no heartbeat for `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (default 30). It runs before every `bg_worker` start (`./manage.py sweep_stale_tasks`) and on `DICOM_TASK_SWEEP_CRON` (default every minute).

## Orthanc Integration

ADIT uses [Orthanc](https://www.orthanc-server.com/index.php) (open-source DICOM server) as a development and testing tool. Bundled Orthanc instances provide mock PACS environments for local development, automated testing, and protocol validation. Supports full DIMSE (C-FIND, C-MOVE, C-GET, C-STORE) and DICOMweb (WADO-RS, QIDO-RS, STOW-RS) protocols.

## DICOM Libraries

**[pydicom](https://pydicom.github.io/)**: Python library for reading, modifying, and writing DICOM files. ADIT uses it to work with DICOM datasets in memory (e.g., `from pydicom import Dataset`), parse DICOM tags, and convert DICOM data to other formats.

**[pynetdicom](https://pydicom.github.io/)**: Python implementation of DICOM networking protocols. ADIT uses it to communicate with remote PACS servers over the network—sending query requests (C-FIND), retrieving images (C-GET/C-MOVE), and accepting incoming DICOM transfers (C-STORE). It handles the low-level network communication while pydicom handles the DICOM file data.

**[dicognito](https://pypi.org/project/dicognito/)**: DICOM anonymization library used for pseudonymization of patient data. ADIT leverages **dicognito** to remove identifying information from DICOM headers, replace patient names/IDs with pseudonyms, and maintain consistency across multiple studies for the same patient. Under the hood, **dicognito** uses **pydicom**.

## Frontend Architecture

Server-side rendered with Django templates and HTMX for dynamic interactions. Uses Bootstrap 5 for styling and Alpine.js for interactive components.

**ADIT Client**: Python package (`adit-client`) for programmatic API access, supporting automated DICOM operations and returning pydicom datasets.

## Docker Container Architecture

ADIT runs as multiple Docker containers that work together. In development, these containers run inside a VS Code **dev container** which provides a consistent development environment with Docker-in-Docker support, allowing you to run and manage the application containers from within the development container.

### Container Types

The Compose project is named `adit_dev` in development and `adit_prod` in production, so the containers are called `adit_dev-<service>-1` (`adit_prod-<service>-1`). All app services share one image and are configured by `docker-compose.base.yml` plus `docker-compose.dev.yml` or `docker-compose.prod.yml`.

**Web Container (`adit_dev-web-1`)**: Runs Django application serving web UI and REST API. Ports: 8000 (dev), 80/443 (prod with SSL). Handles authentication, serves static files, enqueues tasks, and manages database connections. In development its startup command also runs migrations, creates the superuser and example data, and populates the Orthanc servers.

**Init Container (`adit_prod-init-1`)**: Production-only one-shot service that runs `migrate`, `collectstatic`, `create_superuser`, and `retry_stalled_jobs` exactly once before the (possibly replicated) web containers start. In development it is disabled via `profiles: [never]`.

**PostgreSQL Container (`adit_dev-postgres-1`)**: PostgreSQL 17 database storing all data (users, jobs, tasks, logs, Procrastinate queue). Port 5432. Uses Docker volumes for persistence.

**Default Worker Container (`adit_dev-default_worker-1`)**: Processes background tasks in the `default` queue: disk space checks, database backups, `queue_mass_transfer_tasks`, `retry_stalled_jobs`, and the periodic stale task sweep.

**DICOM Worker Container (`adit_dev-dicom_worker-1`)**: Executes DICOM transfer tasks from the `dicom` queue. Multiple instances can run for scaling (`DICOM_WORKER_REPLICAS`).

**Mass Transfer Worker Container (`adit_dev-mass_transfer_worker-1`)**: Executes mass transfer tasks from the `mass_transfer` queue (`MASS_TRANSFER_WORKER_REPLICAS`).

Every worker runs `./manage.py sweep_stale_tasks` before starting `bg_worker`.

**C-STORE Receiver Container (`adit_dev-receiver-1`)**: Accepts incoming DICOM data from C-MOVE operations. Ports: 11112 (DICOM, published as 11122 on the host in development and as `RECEIVER_PORT` in production), 14638 (file transmit). Forwards data to workers via TCP.

**Orthanc Containers (`adit_dev-orthanc1-1`, `adit_dev-orthanc2-1`)**: Development PACS instances for testing. Official Orthanc image. DICOM ports 7501/7502 (published on the host in development only); their HTTP/DICOMweb ports 6501/6502 are internal and reachable in the web UI through a reverse proxy. Uses SQLite for development.

## Application Architecture

### Core Django Apps Structure

#### **Core App** (`adit.core`)

- **Purpose**: Foundation services and shared components
- **Components**: User management, DICOM node configuration, base models, utilities
- **Key Features**: Authentication, authorization, DICOM server management

#### **Transfer Apps**

- **Batch Transfer** (`adit.batch_transfer`): Bulk data transfer operations
- **Selective Transfer** (`adit.selective_transfer`): Individual study transfers
- **Mass Transfer** (`adit.mass_transfer`): Filter-driven export of every matching series in a date range. A `MassTransferJob` (date range, partition granularity, filters, pseudonymization settings) is split into one `MassTransferTask` per daily or weekly partition, and each discovered series is tracked as a `MassTransferVolume`. Runs on its own `mass_transfer` queue.

#### **Exploration & Discovery**

- **DICOM Explorer** (`adit.dicom_explorer`): Interactive DICOM data browsing
- **Batch Query** (`adit.batch_query`): Bulk DICOM server queries

#### **Upload System** (`adit.upload`)

- **File Upload**: Direct DICOM file upload to ADIT

#### **DICOMweb API** (`adit.dicom_web`)

- **Server-side DICOMweb**: QIDO-RS (query), WADO-RS (retrieve, also as NIfTI), and STOW-RS (store) endpoints in front of the configured DICOM servers, used by the ADIT Client. `DicomWebSettings` carries the `can_query`, `can_retrieve`, and `can_store` permissions; `APIUsage` records request counts and transferred bytes per user.

## Primary Models

### User Management

- **Users & Groups**: Django authentication (provided by `adit_radis_shared.accounts`) with group-based access. Each user has an active group, and `DicomNodeGroupAccess` records per group which DICOM nodes may be used as source and/or destination; the active group determines which nodes a user can pick.

- **Permissions**: Fine-grained access control via Django model permissions: `can_process_urgently` (jobs), `can_transfer_unpseudonymized` (transfer jobs), `selective_transfer.can_download_study`, `dicom_web.can_query` / `can_retrieve` / `can_store`, `upload.can_upload_data`, and `dicom_explorer.query_dicom_server`.

### Transfer Operations

Transfer Jobs define transfer operations with owner and status tracking, containing one or more Transfer Tasks that specify study/series/instance operations. Each task progresses through the `DicomTask.Status` states `PENDING`, `IN_PROGRESS`, `CANCELED`, `SUCCESS`, `WARNING`, or `FAILURE`. The job status (`DicomJob.Status`: `UNVERIFIED`, `PENDING`, `IN_PROGRESS`, `CANCELING`, `CANCELED`, `SUCCESS`, `WARNING`, `FAILURE`) is derived from its tasks by `post_process()`: a job with pending tasks is `PENDING`, with running tasks `IN_PROGRESS`, and once all tasks are finished the combination of successful, warning, failed, and canceled tasks decides the final status.

### DICOM Configuration

DICOM Servers represent remote PACS/Orthanc instances, with DICOM Nodes defining source and destination configurations. The system supports both DIMSE protocols (C-FIND, C-GET, C-MOVE, C-STORE) and DICOMweb REST APIs (QIDO-RS, WADO-RS, STOW-RS). Downloading data from a DICOM server can be done by using a DIMSE operation or by using DICOMweb REST calls. When using DIMSE operations C-GET is prioritized over C-MOVE as a worker can fetch the DICOM data directly from the server. When downloading data using a C-MOVE operation, ADIT commands the source DICOM server to send the data to a C-STORE SCP server of ADIT running in a separate container (Receiver) that receives the DICOM data and sends it back to the worker over a TCP socket (`FileTransmitServer` in the receiver, `FileTransmitClient` in the worker; see `adit/core/utils/file_transmit.py`).

## Related Projects

- **ADIT Radis Shared**: Common library providing authentication, utilities, and shared Django apps for ADIT and RADIS

---
