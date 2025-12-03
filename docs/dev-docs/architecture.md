# **ADIT Architecture Documentation**

This document provides a comprehensive overview of ADIT's architecture, implementation details, and key components for developers.

## System Overview

ADIT (Automated DICOM Transfer) is a full-stack web application designed for automated DICOM transfers. The system consists of a Django-based backend, PostgreSQL database, and server-side rendered web interface enhanced with HTMX for dynamic interactions. It provides both web UI and programmatic API access for DICOM data management and transfer operations.

The architecture follows a task-queue pattern where transfer operations are broken down into discrete tasks, queued in the database, and processed by background workers running in separate Docker containers.

## High-Level Architecture

```mermaid

flowchart LR

    UserBrowser["User Browser"]
    WebUI["ADIT Web UI<br/>(Django Templates + HTMX)"]
    DjangoAPI["Django API Server"]
    Worker["Transfer Worker<br/>(Docker)"]
    DB["PostgreSQL Database"]
    CStore["C-STORE Receiver"]
    DICOM["DICOM Servers<br/>(PACS / DICOMweb)"]

    UserBrowser --> WebUI --> DjangoAPI
    DjangoAPI --> Worker
    DjangoAPI --> DB
    Worker --> DB
    Worker --> CStore
    DICOM --> CStore

```

The ADIT platform consists of several coordinated components that together enable automated DICOM retrieval, transformation, and transfer. Users interact with ADIT through a standard web browser, initiating actions such as creating transfer jobs, uploading DICOM files configuring destinations, and monitoring job activity. The browser loads the ADIT Web UI, a server-side rendered interface built with Django templates and enhanced with HTMX for dynamic interactions presenting dashboards, validating input, and providing seamless user experience through partial page updates. Real-time communication for selective transfers uses WebSocket connections. These requests are served by the Django API Server, which provides all REST endpoints and implements business logic including authentication, job orchestration, task creation, configuration handling, and interaction with the PostgreSQL database. PostgreSQL stores all persistent system data such as user accounts, transfer jobs, DICOM query results logs, and configuration, and is regularly polled by Transfer Workers for tasks requiring execution. Transfer Workers running in Docker containers, perform the actual data operations: querying remote DICOM servers, retrieving images via C-GET, C-MOVE, or DICOMweb applying pseudonymization or transformation rules, sending images to destinations, and updating task status. For workflows involving C-MOVE, ADIT also runs a C-STORE Receiver which accepts inbound DICOM objects from PACS, forwards them reliably to the Transfer Worker, and ensures lossless data flow. External DICOM systems such as PACS, VNAs, and DICOMweb servers function as the data sources and sinks, providing and receiving DICOM objects through standard DIMSE and DICOMweb protocols.

## Backend Architecture

### Web/API Server Layer

The backend is built using Django, which acts as the central coordination engine for the platform. It provides REST API endpoints, handles authentication, and manages all persistent data operations. Django serves static assets and orchestrates background task execution.

Key responsibilities include:

Managing users, sessions, and permissions

Exposing API endpoints to the frontend and external systems

Creating job and task records in PostgreSQL

Performing validation and business logic

Scheduling background work for transfer workers

## Database Integration

Django communicates directly with PostgreSQL, which acts as the system of record.
The database stores all job states, study metadata, transfer logs, and configuration needed for workers to operate.

PostgreSQL maintains:

User accounts and access policies

Transfer job definitions and states

DICOM node configuration (AET, IPs, ports)

Task queue entries and execution history

Query results and study metadata extracted from PACS

## Background Processing Layer

The background processing environment consists of multiple worker containers responsible for executing DICOM operations.
These workers continuously poll the database for tasks, perform network transfers, and update progress for the UI.

Transfer workers handle:

C-GET, C-MOVE, and DICOMweb retrieval

File transformations such as pseudonymization

Streaming incoming files from C-STORE receiver

Retrying failed tasks with configurable backoff

Writing detailed logs back into PostgreSQL

### Procrastinate Task Queue System

ADIT uses Procrastinate as its PostgreSQL-based task queue system, providing robust asynchronous job processing with advanced features for reliability and monitoring.

#### Procrastinate Architecture

**Task Definition and Registration**:

- Tasks are defined as Python functions with decorators
- Jobs are serialized and stored directly in PostgreSQL tables
- No external message broker required (Redis, RabbitMQ, etc.)
- Type-safe task parameters using Python type hints

**Queue Management Features**:

- **Job Scheduling**: Support for delayed execution and cron-like scheduling
- **Job Prioritization**: Tasks can be assigned priority levels for execution order
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Job Cancellation**: Ability to cancel queued or running jobs
- **Dead Letter Queue**: Failed jobs after max retries are moved to a separate queue

**Worker Process Management**:

- **Multiple Workers**: Scale horizontally by running multiple worker processes
- **Worker Pools**: Each worker can handle multiple concurrent tasks
- **Graceful Shutdown**: Workers complete current tasks before stopping
- **Health Monitoring**: Built-in health checks and worker status reporting

#### ADIT-Specific Procrastinate Implementation

**Transfer Task Types**:

- `process_dicom_task`: Core DICOM transfer operations for all transfer types
- `check_disk_space`: Periodic monitoring of available disk space
- `retry_stalled_jobs`: Automatic recovery of stalled Procrastinate jobs
- `broadcast_mail`: Email notifications to users and administrators

**Task Flow Management**:

```mermaid

flowchart LR
    A[Django API]
    B[Procrastinate]
    C[Worker Container]
    D[PostgreSQL]

    A -- enqueue --> B
    B -- poll --> C

    A -- status updates --> B
    C -- progress/results --> D

```

**Configuration and Monitoring**:

- **Task Timeouts**: Configurable per-task execution limits
- **Concurrency Control**: Limit concurrent tasks per worker
- **Job History**: Complete audit trail of all task executions
- **Metrics Integration**: Prometheus/Grafana compatible metrics

## DICOM Transfer Implementation

The DICOM transfer system supports multiple communication protocols and flexible data-flow patterns to accommodate both direct and transform-based workflows. It is designed to integrate with PACS environments using traditional DIMSE operations as well as modern DICOMweb services.

Protocol Support

ADIT enables several transfer mechanisms, each suited for different infrastructure needs:

C-GET Operations – Direct pull of DICOM objects from the source PACS (preferred when supported).

C-MOVE Operations – Indirect transfers using a dedicated C-STORE receiver.

DICOMweb REST API – HTTP-based retrieval for systems exposing WADO-RS/QIDO-RS/ STOW-RS.

C-STORE – Used by the receiver component to ingest pushed DICOM datasets.

### Data Pipeline Flow

The system can operate in two primary modes depending on whether processing or anonymization occurs:

#### Direct Transfer Path

Source → Worker → Destination

Optimal for unmodified, pass-through DICOM data.

#### Transform Pipeline

Source → Worker Storage → Transform Step → Destination → Cleanup

Used when transformations, validations, or anonymization are required.

## Orthanc Integration

ADIT integrates with Orthanc, an open-source DICOM server, to provide enhanced DICOM storage, processing, and web-based access capabilities. Orthanc serves as both a development tool and a production component for certain ADIT deployments.

### Orthanc as DICOM Server

**Core Capabilities**:

- **DICOM Storage**: Acts as a lightweight PACS for development and testing
- **Protocol Support**: Full DIMSE (C-FIND, C-MOVE, C-GET, C-STORE) implementation
- **DICOMweb Services**: Built-in WADO-RS, QIDO-RS, and STOW-RS endpoints
- **Web Interface**: Browser-based DICOM viewer and management interface

**ADIT Integration Points**:

- **Development Environment**: Bundled Orthanc instance for local development
- **Testing Backend**: Automated tests use Orthanc as mock PACS
- **Reference Implementation**: Demonstrates DICOM protocol compliance
- **Destination Target**: Can serve as transfer destination for testing

### Orthanc Configuration in ADIT

**Docker Compose Integration**:

```yaml
orthanc1:
  image: jodogne/orthanc-plugins:1.12.9
  hostname: orthanc1.local
  ports:
    - "7501:7501" # DICOM port
```

**Configuration Features**:

- **AE Title Configuration**: Customizable Application Entity settings
- **Storage Backend**: PostgreSQL or SQLite database options
- **Plugin Architecture**: Extensible with DICOMweb and other plugins
- **Security Settings**: Authentication and access control configuration

### Development Workflow with Orthanc

**Local Development Setup**:

1. **Mock PACS**: Orthanc provides a complete PACS environment
2. **Test Data Upload**: Sample DICOM files can be uploaded via web interface
3. **Transfer Testing**: ADIT can query and transfer from local Orthanc
4. **Protocol Validation**: Verify DIMSE and DICOMweb implementations

**Integration Testing**:

- **Automated Tests**: Use Orthanc as source and destination for transfers
- **Protocol Compliance**: Validate C-FIND, C-MOVE, and C-GET operations
- **Performance Testing**: Measure transfer speeds and concurrent connections
- **Error Handling**: Test timeout, retry, and failure scenarios

## Frontend Architecture

The ADIT frontend is designed to provide an intuitive user experience for managing DICOM transfers, browsing studies, and interacting with the system through a modern web interface. It consists of a client-side application built with standard web technologies and a REST API layer that enables both human and programmatic access.

### Web User Interface

ADIT uses a server-side rendered web interface built with Django templates and enhanced with HTMX for dynamic interactions. The frontend emphasizes simplicity and maintainability while providing a responsive user experience for DICOM data management.

### Technology Stack

**Server-Side Rendering**: Django templates with template inheritance for clean, maintainable HTML

**Dynamic Interactions**: HTMX for partial page updates, modals, and asynchronous requests without heavy JavaScript frameworks

**CSS Framework**: Bootstrap 5 for responsive design and consistent UI components

**JavaScript Libraries**: Minimal vanilla JavaScript with Alpine.js for specific interactive components

**Static Assets**: Vendor libraries (Bootstrap, HTMX, Alpine.js) served via Django's staticfiles system

### Key Features

Interactive browser for inspecting DICOM studies

Configuration panels to create and manage transfer jobs

File upload interface for direct ingestion of DICOM datasets

Live status updates showing job progress and transfer metrics

User and role management for access control and permissions

## REST API Architecture

The REST API forms the communication backbone of ADIT, enabling both the web frontend and external tools to perform operations consistently. It adheres to standard API design principles to ensure stability, clarity, and interoperability.

### API Design

RESTful endpoint structure covering all core system capabilities

JSON used for all input/output payloads

Authentication supported via sessions or token-based mechanisms

Robust error handling with well-defined HTTP status codes

Rate limiting and request validation to ensure reliability and security

### ADIT Client Library

**ADIT Client** is a separate Python package (`adit-client`) that provides programmatic access to ADIT's REST API:

- **Scripted Operations**: Enables automated DICOM queries, transfers, and batch operations
- **API Integration**: Uses the same REST endpoints as the web interface
- **DICOM Support**: Returns pydicom datasets for seamless integration with DICOM workflows
- **Authentication**: Token-based authentication for secure API access
- **Documentation**: Comprehensive examples and usage patterns for system integration

## Docker Container Architecture

ADIT employs a multi-container Docker architecture that provides service isolation, scalability, and consistent deployment across environments. The containerized design allows for independent scaling of components and simplified dependency management.

### Container Overview

ADIT typically runs with the following container types in a production deployment:

```mermaid
flowchart TB
    subgraph "ADIT Platform"
        subgraph "Core Services"
            WEB["Web/API Container<br/>(Direct SSL via Daphne)"]
            DB["PostgreSQL Container<br/>(adit-db)"]
        end

        subgraph "Worker Layer"
            W1["Transfer Worker 1<br/>(adit-worker)"]
            W2["Transfer Worker 2<br/>(adit-worker)"]
            WN["Transfer Worker N<br/>(adit-worker)"]
        end

        subgraph "DICOM Services"
            REC["C-STORE Receiver<br/>(adit-receiver)"]
            ORTH1["Orthanc Server 1<br/>(orthanc1)"]
            ORTH2["Orthanc Server 2<br/>(orthanc2)"]
        end

        subgraph "Storage"
            VOL[("Shared Volumes")]
        end
    end

    subgraph "External Access"
        HTTPS["HTTPS:443"]
        HTTP["HTTP:80"]
        DICOM_PORT["DICOM:11112"]
    end

    HTTPS --> WEB
    HTTP --> WEB
    DICOM_PORT --> REC

    WEB --> DB
    W1 --> DB
    W2 --> DB
    WN --> DB
    W1 --> REC
    W2 --> REC
    WN --> REC
    WEB --> VOL
    W1 --> VOL
    W2 --> VOL
    WN --> VOL
```

### Core Service Containers

#### Web/API Container (`adit-web`)

**Purpose**: Hosts the Django application serving both web UI and REST API

**Configuration**:

- **Base Image**: Python 3.13 with Django dependencies and Daphne ASGI server
- **Exposed Ports**:
  - **Development**: 8000 (HTTP), 5678 (remote debugging)
  - **Production**: 80 (HTTP), 443 (HTTPS with SSL termination)
- **SSL Handling**: Direct SSL termination via Daphne with certificate files mounted as volumes
- **Environment**: Production/development configuration via environment variables
- **Health Checks**: Django health check endpoints at `/health/`

**Responsibilities**:

- Serve Django templates and static assets
- Process API requests and authentication
- Enqueue background tasks via Procrastinate
- Database connection management

#### PostgreSQL Container (`adit-db`)

**Purpose**: Primary database for all persistent data

**Configuration**:

- **Base Image**: PostgreSQL 17 with extensions
- **Exposed Ports**: 5432 (PostgreSQL)
- **Persistent Storage**: Docker volume for data persistence
- **Backup Strategy**: Automated dumps and point-in-time recovery

**Database Extensions**:

- **Procrastinate Tables**: Task queue storage
- **DICOM Metadata**: Optimized indexes for study queries
- **Audit Logging**: Transfer history and user actions

### Worker Container Layer

#### Transfer Worker Containers (`adit-worker`)

**Purpose**: Execute DICOM transfer tasks and background processing

**Scaling Strategy**:

- **Horizontal Scaling**: Deploy multiple worker instances
- **Resource Allocation**: CPU and memory limits per container
- **Auto-scaling**: Scale based on queue depth and system load

**Container Configuration**:

- **Base Image**: Same as web container with additional DICOM tools
- **No Exposed Ports**: Workers communicate via database and internal networks
- **Shared Storage**: Access to temporary file storage for transformations
- **Process Management**: Procrastinate worker process with configurable concurrency

**Worker Types and Specialization**:

- **General Workers**: Handle standard transfer operations
- **High-Memory Workers**: For large dataset processing and transformations
- **Specialized Workers**: Dedicated to specific PACS or protocols

### DICOM Service Containers

#### C-STORE Receiver Container (`adit-receiver`)

**Purpose**: Accept incoming DICOM data from C-MOVE operations

**Configuration**:

- **Base Image**: Python 3.13 with pynetdicom and DICOM libraries
- **Internal Ports**: 11112 (DICOM C-STORE SCP), 14638 (File Transmit TCP)
- **External Ports**:
  - **Development**: 11122:11112 (mapped to avoid conflicts)
  - **Production**: 11112:11112 (direct mapping)
- **Network**: Internal communication with worker containers via service discovery
- **File Streaming**: High-performance TCP socket connections to transfer workers

**Operational Features**:

- **High Availability**: Multiple receiver instances for load distribution
- **Connection Pooling**: Efficient handling of concurrent C-STORE associations
- **Error Recovery**: Automatic retry and failover mechanisms

#### Orthanc Container (`orthanc`)

**Purpose**: Development PACS and DICOMweb services

**Configuration**:

- **Base Image**: Official Orthanc Docker image
- **Exposed Ports**: 7501/7502 (DICOM only in development setup)
- **Storage**: PostgreSQL backend for production, SQLite for development
- **Plugins**: DICOMweb, authentication, and storage plugins

### Infrastructure Containers

#### Web/API Container SSL Handling

**Purpose**: Direct SSL termination and request handling via Django/Daphne

**Features**:

- **SSL/TLS**: Direct SSL termination using Daphne ASGI server with certificate files
- **Load Balancing**: Multiple web container replicas managed by container orchestration
- **Static Files**: Served by Django's staticfiles system
- **Health Checks**: Built-in Django health check endpoints

### Container Orchestration

#### Docker Compose Configuration

**Development Environment**:

```yaml
services:
  web:
    image: adit_dev:latest
    ports:
      - ${WEB_DEV_PORT:-8000}:8000
      - ${REMOTE_DEBUGGING_PORT:-5678}:5678
    command: >
      bash -c "
        wait-for-it -s postgres.local:5432 -t 60 && 
        ./manage.py migrate &&
        ./manage.py create_superuser &&
        ./manage.py create_example_users &&
        ./manage.py create_example_groups &&
        ./manage.py populate_example_data &&
        wait-for-it -s orthanc1.local:6501 -t 60 &&
        ./manage.py populate_orthancs &&
        ./manage.py retry_stalled_jobs &&
        ./manage.py runserver 0.0.0.0:8000
      "
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]

  default_worker:
    image: adit_dev:latest
    command: >
      bash -c "
        wait-for-it -s postgres.local:5432 -t 60 &&
        ./manage.py bg_worker -l debug -q default --autoreload
      "

  dicom_worker:
    image: adit_dev:latest
    command: >
      bash -c "
        wait-for-it -s postgres.local:5432 -t 60 &&
        ./manage.py bg_worker -l debug -q dicom --autoreload
      "

  receiver:
    image: adit_dev:latest
    ports:
      - 11122:11112
    command: |
      ./manage.py receiver --autoreload

  postgres:
    image: postgres:17
    environment:
      POSTGRES_PASSWORD: postgres
    ports:
      - ${POSTGRES_DEV_PORT:-5432}:5432

  orthanc1:
    image: jodogne/orthanc-plugins:1.12.9
    ports:
      - "7501:7501"

  orthanc2:
    image: jodogne/orthanc-plugins:1.12.9
    ports:
      - "7502:7502"
```

**Production Environment**:

```yaml
services:
  web:
    image: ghcr.io/openradx/adit:latest
    ports:
      - ${WEB_HTTP_PORT:-80}:80
      - ${WEB_HTTPS_PORT:-443}:443
    command: >
      bash -c "
        wait-for-it -s init.local:8000 -t 300 && 
        echo 'Starting web server ...' &&
        daphne -b 0.0.0.0 -p 80 \\
          -e ssl:443:privateKey=/etc/web/ssl/key.pem:certKey=/etc/web/ssl/cert.pem \\
          adit.asgi:application
      "
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost/health/"]
    deploy:
      replicas: ${WEB_REPLICAS:-3}

  default_worker:
    image: ghcr.io/openradx/adit:latest
    command: >
      bash -c "
        wait-for-it -s postgres.local:5432 -t 60 &&
        ./manage.py bg_worker -q default
      "

  dicom_worker:
    image: ghcr.io/openradx/adit:latest
    command: >
      bash -c "
        wait-for-it -s postgres.local:5432 -t 60 &&
        ./manage.py bg_worker -q dicom
      "
    deploy:
      replicas: ${DICOM_WORKER_REPLICAS:-3}

  receiver:
    image: ghcr.io/openradx/adit:latest
    ports:
      - 11112:11112
    command: ./manage.py receiver
```

**Container Orchestration Options**:

- **Docker Swarm**: Built-in orchestration with service replicas and load balancing
- **Kubernetes**: Advanced orchestration with auto-scaling and service mesh integration
- **Monitoring**: Prometheus, Grafana, and log aggregation
- **Backup Strategy**: Automated database backups and disaster recovery

#### Resource Management

**Resource Allocation**:

- **Web Container**: 2 CPU cores, 4GB RAM (baseline)
- **Worker Containers**: 1-2 CPU cores, 2-8GB RAM (depending on workload)
- **Database Container**: 4+ CPU cores, 8+ GB RAM, SSD storage
- **Receiver Container**: 1 CPU core, 1GB RAM (lightweight)

**Storage Requirements**:

- **Database Volume**: Persistent storage for PostgreSQL data
- **Temporary Storage**: Shared volume for DICOM file transformations
- **Log Storage**: Centralized logging with retention policies
- **Backup Storage**: Regular database and configuration backups

#### Networking Architecture

**Internal Networks**:

- **Backend Network**: Web, workers, and database communication via Docker internal networks
- **DICOM Network**: Receiver and external PACS communication
- **Container Network**: All containers communicate via Docker Compose default network

**Security Considerations**:

- **Network Isolation**: Containers communicate only through defined Docker networks
- **SSL Termination**: Direct SSL handling by web container with mounted certificate files
- **Secrets Management**: Database credentials and SSL certificates via Docker volumes and environment variables
- **Image Security**: Regular base image updates and vulnerability scanning
- **Runtime Security**: Non-root user execution and read-only containers where possible

## Application Architecture

### Core Django Apps Structure

#### **Core App** (`adit.core`)

- **Purpose**: Foundation services and shared components
- **Components**: User management, DICOM node configuration, base models, utilities
- **Key Features**: Authentication, authorization, DICOM server management

#### **Transfer Apps**

- **Batch Transfer** (`adit.batch_transfer`): Bulk data transfer operations
- **Selective Transfer** (`adit.selective_transfer`): Individual study transfers
- **Batch Query** (`adit.batch_query`): Bulk DICOM server queries

#### **Exploration & Discovery**

- **DICOM Explorer** (`adit.dicom_explorer`): Interactive DICOM data browsing
- **DICOM Web** (`adit.dicom_web`): RESTful DICOM services interface

#### **Upload System** (`adit.upload`)

- **File Upload**: Direct DICOM file upload to ADIT
- **Batch Processing**: Bulk file import and processing
- **Validation**: DICOM compliance and integrity checking

## Data Architecture

The ADIT data layer models users, DICOM endpoints, transfer workflows, and cached study metadata. Using Django’s ORM, the system ensures relational consistency, auditability, and scalable workflow execution.

---

## Primary Models

### User Management

User-related models extend Django’s built-in authentication system to support DICOM-specific workflows.

- **Users & Groups** – Standard authentication with custom role definitions
- **Permissions** – Fine-grained access control for PACS and transfer operations
- **Profile Extensions** – Additional metadata fields for workflow-specific needs

### DICOM Infrastructure

Models defining connectivity and capability information for external PACS systems.

- **DICOM Nodes** – AE Titles, IP/port, and supported service classes
- **Connection Profiles** – Authentication and protocol settings
- **Server Capabilities** – Supported DIMSE and DICOMweb operations

### Transfer Operations

Models responsible for describing, tracking, and auditing transfers.

- **Transfer Jobs** – High-level transfer definitions
- **Transfer Tasks** – Atomic operations for study/series/instance transfer
- **Task Status** – Structured progress and error tracking
- **Transfer History** – Logs and audit trails for completed operations

### Study Management

Cached metadata for efficient querying and validation.

- **Study Metadata** – Basic cached DICOM study-level information
- **Series Tracking** – Individual series belonging to each study
- **Instance Management** – Instance-level tracking and operations

---

## Authentication & Authorization

ADIT uses Django’s security model combined with custom rules for DICOM-specific access control.

### Security Model

- **Django Auth System** – Core authentication with extensions
- **Group-based Permissions** – Role-based access control
- **DICOM Node Access** – User-level restrictions for PACS endpoints
- **Session Management** – Secure sessions with configurable timeout

### Access Control

- **Operation-level Permissions** – Controls who can run transfers
- **Data Access Restrictions** – Limits visibility to specific studies or nodes
- **Audit Logging** – Tracks sensitive actions and data access events

---

## Performance & Scalability

The system is engineered for high-volume and high-concurrency DICOM data processing.

### Asynchronous Processing

- **Background Jobs** – Offloads time-consuming tasks
- **Worker Scaling** – Horizontal scaling for high throughput
- **Queue Management** – Efficient distribution via Procrastinate
- **Resource Optimization** – Balanced memory and storage usage

### Database Optimization

- **Connection Pooling** – Improves query efficiency
- **Query Optimization** – Indexed and optimized queries
- **Data Partitioning** – Scalable long-term storage strategies
- **Cleanup Processes** – Automatic removal of old logs and temporary data

### Monitoring & Observability

- **Transfer Status Tracking** – Real-time job/task updates
- **Performance Metrics** – Throughput and reliability indicators
- **Error Handling** – Structured exception logging
- **Health Checks** – Ensures all components remain operational

---

## Development & Deployment

A containerized architecture supports reproducible environments and scalable deployments.

### Containerization Strategy

- **Multi-container Architecture** – Web, worker, and database isolation
- **Docker Compose** – Unified orchestration for dev and prod
- **Environment Configuration** – Environment-variable based settings
- **Volume Management** – Persistent storage for DB and temp files

### API Integration Points

- **External PACS Integration** – Full DICOM protocol support
- **DICOMweb Services** – REST-based imaging operations
- **Client Libraries** – Python SDK with examples
- **Webhook Support** – Event-driven integrations

---

This structure provides a scalable, secure, and extensible foundation for ADIT’s DICOM data exchange workflows
