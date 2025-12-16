# **ADIT Architecture Documentation**

This document provides a comprehensive overview of ADIT's architecture, implementation details, and key components for developers.

## System Overview

ADIT (Automated DICOM Transfer) is a full-stack web application designed for automated DICOM transfers. The system consists of a Django-based backend, PostgreSQL database, and server-side rendered web interface enhanced with HTMX for dynamic interactions.

ADIT inherits common functionality from **ADIT Radis Shared**, a shared library that provides core components including user authentication, token-based authentication, common utilities, and shared Django applications used by both ADIT and RADIS projects.

## High-Level Architecture

The ADIT platform provides automated DICOM retrieval, transformation, and transfer through coordinated Docker containers. Users access the system via **web browser** or **ADIT Client** (Python library for programmatic access), performing operations such as creating transfer jobs, uploading DICOM files, and configuring destinations.

The system consists of three main components: a Django API server handling web UI and orchestration, a PostgreSQL database storing all persistent data and serving as the task queue, and transfer workers executing DICOM operations in the background.

## Backend Architecture

**Django Web/API Server**: Central coordination engine providing REST API endpoints, authentication, user/session management, static assets, and task orchestration. Creates job/task records in PostgreSQL and schedules background work.

**PostgreSQL Database**: System of record storing user accounts, transfer jobs, DICOM node configuration, task queue entries, execution history, and study metadata.

**Transfer Workers**: Docker containers polling PostgreSQL for tasks, executing C-GET/C-MOVE/DICOMweb operations, applying pseudonymization, and logging results.

### Procrastinate Task Queue System

ADIT uses [Procrastinate](https://procrastinate.readthedocs.io/en/stable/), a PostgreSQL-based task queue storing jobs directly in the database without external message brokers. Tasks are Python functions with decorators, supporting job scheduling, prioritization, retry logic with exponential backoff, cancellation, and dead letter queues. Workers scale horizontally with configurable concurrency, graceful shutdown, and health monitoring.

**ADIT Task Types**: `process_dicom_task` (core transfers), `check_disk_space`, `backup_db`.
Features include configurable timeouts (20-minute process timeout), concurrency control via queue management, complete job history and logs in PostgreSQL, retry logic with exponential backoff (max 3 attempts), and graceful error handling.

## Orthanc Integration

ADIT uses [Orthanc](https://www.orthanc-server.com/index.php) (open-source DICOM server) as a development and testing tool. Bundled Orthanc instances provide mock PACS environments for local development, automated testing, and protocol validation. Supports full DIMSE (C-FIND, C-MOVE, C-GET, C-STORE) and DICOMweb (WADO-RS, QIDO-RS, STOW-RS) protocols.

## DICOM Libraries

**pydicom**: Python library for reading, modifying, and writing DICOM files. ADIT uses it to work with DICOM datasets in memory (e.g., `from pydicom import Dataset`), parse DICOM tags, modify patient information for pseudonymization, and convert DICOM data to other formats.

**pynetdicom**: Python implementation of DICOM networking protocols. ADIT uses it to communicate with remote PACS servers over the network—sending query requests (C-FIND), retrieving images (C-GET/C-MOVE), and accepting incoming DICOM transfers (C-STORE). It handles the low-level network communication while pydicom handles the DICOM file data.

## Frontend Architecture

Server-side rendered with Django templates and HTMX for dynamic interactions. Uses Bootstrap 5 for styling and Alpine.js for interactive components.

**ADIT Client**: Python package (`adit-client`) for programmatic API access, supporting automated DICOM operations and returning pydicom datasets.

## Docker Container Architecture

ADIT runs as multiple Docker containers that work together. In development, these containers run inside a VS Code **dev container** which provides a consistent development environment with Docker-in-Docker support, allowing you to run and manage the application containers from within the development container.

### Container Types

**Web Container (`adit-web-1`)**: Runs Django application serving web UI and REST API. Python 3.13 with Daphne ASGI server. Ports: 8000 (dev), 80/443 (prod with SSL). Handles authentication, serves static files, enqueues tasks, and manages database connections.

**PostgreSQL Container (`adit-postgres-1`)**: PostgreSQL 17 database storing all data (users, jobs, tasks, logs, Procrastinate queue). Port 5432. Uses Docker volumes for persistence.

**Default Worker Container (`adit-default_worker-1`)**: Processes background tasks in the default queue (e.g., disk space checks, database backups).

**DICOM Worker Container (`adit-dicom_worker-1`)**: Executes DICOM transfer tasks from the dicom queue. Same base image as web container plus DICOM tools. Multiple instances can run for scaling.

**C-STORE Receiver Container (`adit-receiver-1`)**: Accepts incoming DICOM data from C-MOVE operations. Python 3.13 with pynetdicom. Ports: 11112 (DICOM), 14638 (file transmit). Forwards data to workers via TCP.

**Orthanc Containers (`adit-orthanc1-1`, `adit-orthanc2-1`)**: Development PACS instances for testing. Official Orthanc image. Ports 7501/7502 (dev only). Uses SQLite for development.

### Dev Container

The [Dev Container](https://code.visualstudio.com/docs/devcontainers/create-dev-container) is a Docker container that provides the development environment (VS Code, Git, Docker CLI, Node.js, Python tools). It uses Docker-in-Docker to run the application containers inside it. This ensures all developers have identical environments and can manage ADIT's multi-container setup seamlessly.

## Application Architecture

### Core Django Apps Structure

#### **Core App** (`adit.core`)

- **Purpose**: Foundation services and shared components
- **Components**: User management, DICOM node configuration, base models, utilities
- **Key Features**: Authentication, authorization, DICOM server management

#### **Transfer Apps**

- **Batch Transfer** (`adit.batch_transfer`): Bulk data transfer operations
- **Selective Transfer** (`adit.selective_transfer`): Individual study transfers

#### **Exploration & Discovery**

- **DICOM Explorer** (`adit.dicom_explorer`): Interactive DICOM data browsing
- **Batch Query** (`adit.batch_query`): Bulk DICOM server queries

#### **Upload System** (`adit.upload`)

- **File Upload**: Direct DICOM file upload to ADIT

## Primary Models

### User Management

- **Users & Groups**: Django authentication with role definitions
- **Permissions**: Access control for PACS operations

### Transfer Operations

Transfer Jobs define transfer operations with owner and status tracking, containing one or more Transfer Tasks that specify study/series/instance operations. Each task progresses through states: PENDING, IN_PROGRESS, SUCCESS, FAILURE, or CANCELED.

### DICOM Configuration

DICOM Servers represent remote PACS/Orthanc instances, with DICOM Nodes defining source and destination configurations. The system supports both DIMSE protocols (C-FIND, C-GET, C-MOVE, C-STORE) and DICOMweb REST APIs (QIDO-RS, WADO-RS, STOW-RS).

## Related Projects

- **ADIT Radis Shared**: Common library providing authentication, utilities, and shared Django apps for ADIT and RADIS

---
