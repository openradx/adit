# Admin Guide

The Admin Guide is intended for system administrators and technical staff responsible for configuring, and maintaining ADIT for DICOM data transfer.

## Installation

ADIT runs in production as a Docker Swarm stack. The `cli` helper (run through `uv`) wraps the required Docker commands.

1. **Clone the repository** and install the CLI dependencies:

    ```bash
    git clone https://github.com/openradx/adit.git
    cd adit
    uv sync
    ```

2. **Create the `.env` file** from `example.env`:

    ```bash
    uv run cli init-workspace
    ```

3. **Edit `.env`** for your deployment. At least set `ENVIRONMENT=production`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `SITE_DOMAIN`, `CALLING_AE_TITLE`, `RECEIVER_AE_TITLE`, the SSL certificate files, the ports and the email settings (see [Environment Variables](#environment-variables)). Generate the secrets with `uv run cli generate-django-secret-key`, `uv run cli generate-secure-password` and `uv run cli generate-auth-token` and paste them into `.env` (`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `TOKEN_AUTHENTICATION_SALT`, `SUPERUSER_PASSWORD`, `SUPERUSER_AUTH_TOKEN`).

4. **Pull the Docker image** (the image set in `ADIT_IMAGE`, by default `ghcr.io/openradx/adit:latest`):

    ```bash
    uv run cli compose-pull
    ```

5. **Deploy the stack**:

    ```bash
    uv run cli stack-deploy
    ```

!!! warning "No quotes in .env"
    Values in `.env` must not be wrapped in quotes. The file is passed to the containers as is, and Docker Swarm treats the quotes as part of the value. `stack-deploy` refuses to run when it finds quoted values, and it only runs when `ENVIRONMENT=production`.

### Environment Variables

All settings are read from the `.env` file. The comments in `example.env` are the authoritative reference; the most important variables are:

| Variable | Meaning | Default in `example.env` |
|---|---|---|
| `ENVIRONMENT` | `development` or `production`. Selects the compose file and Django settings | `development` |
| `ADIT_IMAGE` | Docker image used for the app services. Override to run a locally built image (e.g. for staging) | `ghcr.io/openradx/adit:latest` (commented out) |
| `STACK_NAME` | Name of the Docker Swarm stack. Also used to derive unique session and CSRF cookie names for multiple stacks on one host | `adit_prod` / `adit_dev` (commented out) |
| `WEB_HTTP_PORT`, `WEB_HTTPS_PORT`, `RECEIVER_PORT` | Host ports of the web server and the C-STORE receiver in production | `80`, `443`, `11112` |
| `WEB_DEV_PORT`, `POSTGRES_DEV_PORT` | Host ports mapped during development | `8000`, `5432` |
| `DJANGO_SECRET_KEY` | Key used for cryptographic signing. Must be unique and secret | placeholder |
| `POSTGRES_PASSWORD` | Database password (production only) | placeholder |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names ADIT may be served under | `localhost,127.0.0.1` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins (with scheme) trusted for CSRF, e.g. `https://adit.example.com` | empty |
| `DJANGO_INTERNAL_IPS` | IPs that see debug information (development only) | `127.0.0.1` |
| `DJANGO_SECURE_SSL_REDIRECT` | Redirect all HTTP requests to HTTPS (production only) | `true` |
| `TOKEN_AUTHENTICATION_SALT` | Salt used to hash API tokens. Changing it invalidates all existing tokens | placeholder |
| `DJANGO_SERVER_EMAIL`, `DJANGO_EMAIL_URL` | Sender address and SMTP URL for emails to users and admins. In development emails are logged to the console | `server@example-project.example`, `smtp://localhost:25` |
| `DJANGO_ADMIN_EMAIL`, `DJANGO_ADMIN_FULL_NAME` | Admin who receives critical error notifications and account approval requests | `admin@adit.example`, `ADIT Admin` |
| `SUPPORT_EMAIL` | Support address shown to users | `support@adit.example` |
| `SUPERUSER_USERNAME`, `SUPERUSER_EMAIL`, `SUPERUSER_PASSWORD`, `SUPERUSER_AUTH_TOKEN` | Superuser created on startup (with an optional API token) | `superuser`, placeholders |
| `BACKUP_DIR` | Host folder for database backups | `./.docker-data/backups` |
| `BACKUP_ENABLED`, `BACKUP_CRON` | Enable the periodic database backup and its schedule | `true`, `0 3 * * *` |
| `SITE_NAME`, `SITE_DOMAIN` | Site name and domain used by the Django sites framework (e.g. in emails) | `ADIT`, `localhost` |
| `SSL_HOSTNAME`, `SSL_IP_ADDRESSES` | Hostname and IPs written into a generated self-signed certificate (`uv run cli generate-certificate-files`) | `localhost`, `127.0.0.1` |
| `SSL_SERVER_CERT_FILE`, `SSL_SERVER_KEY_FILE`, `SSL_SERVER_CHAIN_FILE` | Certificate, key and chain files mounted into the web container (production only). Use `uv run cli generate-certificate-chain` for a certificate signed by your CA | `./cert.pem`, `./key.pem`, `./chain.pem` |
| `TIME_ZONE` | Time zone of the server | `Europe/Berlin` |
| `WAIT_POSTGRES_TIMEOUT` | Seconds the containers wait for PostgreSQL on startup | `180` |
| `CALLING_AE_TITLE` | AE title ADIT uses when calling DICOM servers. Required, no default | `ADIT1DEV` |
| `RECEIVER_AE_TITLE` | AE title of the C-STORE receiver (the target of C-MOVE). Required, no default | `ADIT1DEV` |
| `EXCLUDE_MODALITIES` | Comma-separated modalities skipped when a study is transferred or downloaded pseudonymized through the web interface (does not affect the ADIT client) | `PR,SR` |
| `WEB_REPLICAS`, `DICOM_WORKER_REPLICAS`, `MASS_TRANSFER_WORKER_REPLICAS` | Number of replicas of the web server, the DICOM workers and the mass transfer workers (production) | `5`, `3`, `5` |
| `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` | Seconds without a worker heartbeat before a task in progress counts as abandoned. Never set below 30 | `30` |
| `DICOM_TASK_SWEEP_CRON` | Schedule (cron syntax) of the sweep that repairs abandoned tasks | `* * * * *` |
| `MOUNT_DIR` | Host directory that contains the download folders (mounted as `/mnt` in the containers, see [Folder Management](#folder-management)) | `./.docker-data/mount` |
| `ANONYMIZATION_SEED` | Seed for the client-side pseudonymization in the upload portal. Required | `123456789` |
| `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` | Proxy settings for the containers. `NO_PROXY` must contain `.local` | commented out |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP HTTP endpoint of an OpenTelemetry collector | `http://otel-collector.local:4318` |

## Updating ADIT

Follow these steps to safely update your ADIT:

1. **Verify no active jobs**: Navigate to **Admin Section** → **Job Overview** (available at `/admin-section/`) and confirm nothing is pending or in progress
2. **Enable maintenance mode**: In Django Admin, navigate to **Common** → **Project settings** and check the "Maintenance" checkbox, then save
3. **Backup database**: Run `uv run cli db-backup` to create a database backup
4. **Remove stack**: Run `uv run cli stack-rm` to remove all Docker containers and services
5. **Pull latest changes**: Run `git pull origin main` to fetch the latest code updates
6. **Update environment**: Compare `example.env` with your `.env` file and add any new environment variables or update changed values. If you pinned `ADIT_IMAGE` to a specific tag, update it to the version you want to run. Keep `STACK_NAME` unchanged, otherwise a second stack is deployed next to the old one
7. **Pull Docker images**: Run `uv run cli compose-pull` to download the image set in `ADIT_IMAGE`
8. **Deploy stack**: Run `uv run cli stack-deploy` to start all services with the updated image
9. **Disable maintenance mode**: In Django Admin, navigate to **Common** → **Project settings** and uncheck the "Maintenance" checkbox, then save

### Worker Crash Recovery

Tasks are processed by worker containers. When a worker dies (crash, restart, redeploy) while a task is in progress, the task stays in the `In Progress` state. ADIT repairs such tasks automatically: a sweep (`./manage.py sweep_stale_tasks`) runs at every worker start and periodically (`DICOM_TASK_SWEEP_CRON`, every minute by default) and puts every task whose worker sent no heartbeat for `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (30 s by default) back to `Pending` so it is processed again (or to `Canceled` if its job is being canceled). No manual intervention is needed after a worker crash; a task that stays `In Progress` for longer than the grace period plus one sweep interval indicates that the worker is still alive but blocked.

## User and Group Management

Administrators can create users by navigating to the Django Admin section. Alternatively, users can self-register, after which an administrator must approve and activate their account.

ADIT uses a group-based permission system:

- **Groups** define access to specific DICOM servers through source/destination permissions
- **Users** are assigned to one or more groups to inherit their permissions

### Creating and Managing Groups

1. **Access Django Admin**:
   - Log in as a staff user
   - Go to **Admin Section** → **Django Admin** (available at `/django-admin/` URL path)

2. **Create/Edit Groups**:
   - Navigate to **Authentication and Authorization** → **Groups**
   - Click "Add Group" or edit an existing group
   - Give the group a **Name** (e.g., "Radiologists", "Research Team")

3. **Assign Permissions**:
   - In the group form, you'll see **Available permissions** and **Chosen permissions**
   - Select the permissions you want from the available list:
     - `selective_transfer | selective transfer job | Can process urgently`
     - `selective_transfer | selective transfer job | Can transfer unpseudonymized`
     - `batch_transfer | batch transfer job | Can process urgently`
     - `batch_transfer | batch transfer job | Can transfer unpseudonymized`
     - Plus other ADIT-specific permissions for viewing/adding jobs
   - Move them to **Chosen permissions**

4. **Add Users to Group**:
   - In the **Users** section, select users from **Available users**
   - Move them to **Chosen users**
   - Click **Save** to apply all changes

## Server and Folder Management

### Server Management

To add or configure DICOM servers, use the Django Admin interface:

1. Log in as an administrator
2. Go to **Admin Section** → **Django Admin** (available at `/django-admin/` URL path)
3. Navigate to **Core** → **Dicom servers**
4. Click **Add Dicom server**
5. Configure the server details:

   **Basic Settings:**
   - **Name**: Friendly name for the server
   - **Ae title**: DICOM Application Entity title
   - **Host**: Server hostname or IP address
   - **Port**: DICOM port number

   **DICOM Protocol Support:**
   - **Patient root find support**: Enable C-FIND at patient root level
   - **Patient root get support**: Enable C-GET at patient root level
   - **Patient root move support**: Enable C-MOVE at patient root level
   - **Study root find support**: Enable C-FIND at study root level
   - **Study root get support**: Enable C-GET at study root level
   - **Study root move support**: Enable C-MOVE at study root level
   - **Store scp support**: Enable C-STORE SCP operations

   **DICOMweb Settings (if applicable):**
   - **Dicomweb root url**: Base URL for DICOMweb services
   - **Dicomweb qido support**: Enable QIDO-RS (queries)
   - **Dicomweb wado support**: Enable WADO-RS (retrieval)
   - **Dicomweb stow support**: Enable STOW-RS (storage)
   - **Dicomweb qido prefix**: URL prefix for QIDO-RS endpoints
   - **Dicomweb wado prefix**: URL prefix for WADO-RS endpoints
   - **Dicomweb stow prefix**: URL prefix for STOW-RS endpoints
   - **Dicomweb authorization header**: Authentication header for DICOMweb requests

   **Query Settings:**
   - **Max search results**: Maximum number of C-FIND results per query (default 200). When a search hits this limit, ADIT splits the queried time range into smaller windows and searches again

6. **Configure Group Access**: In the **DICOM node group accesses** section, specify which groups can use this server as source or destination

!!! note "DICOM Protocol Support"
    To determine which DICOM protocols are supported by a server, consult the server's DICOM Conformance Statement.

### Folder Management

DICOM folders are destinations on a mounted network drive to which users can download data (instead of transferring it to a server). The folder paths must be located below the directory set in `MOUNT_DIR`, which is mounted as `/mnt` in the containers.

1. **Access Django Admin**: Navigate to **Admin Section** → **Django Admin**
2. **Configure Folders**: Go to **Core** → **Dicom folders**
3. **Add or Edit Folder**:
   - Click **Add dicom folder** to create a new folder configuration
   - Enter a **Name** for the folder (e.g., "Research Downloads")
   - Specify the **Path** where DICOM files should be stored
   - Set the **Quota**: The disk quota of this folder in GB
   - Set the **Warn size**: The used space in GB at which the admins are informed by email
4. **Assign to Groups**: In the **DICOM node group accesses** section, specify which groups can use this folder as destination (a folder is never a source)
5. **Save**: Click **Save** to apply changes

!!! tip "Quota Monitoring"
    Administrators receive an email when the used space of a folder reaches the configured warn size, allowing proactive storage management.

## Job Overview

The **Admin Section** (available at `/admin-section/` for staff users) includes a **Job Overview** table with one row per job type (Selective Transfer, Batch Query, Batch Transfer, Mass Transfer) and one column per status: Unverified, Pending, In Progress, Canceling, Canceled, Success, Warning, Failure. Each cell shows the number of jobs and links to the filtered job list of all users, where you can open individual jobs for details.

Below the Job Overview, the **API Usage** table lists per user the time of the last DICOMweb API request, the total response size and the total number of requests.

### Broadcasting Messages

Administrators can send an email to all users:

1. Navigate to **Admin Section** → **Send Email to all users** (available at `/admin-section/broadcast/`)
2. Enter a subject and the message and send it

## System Announcements

System administrators can inform users about important updates, maintenance schedules, or system changes through the announcement feature.

### Creating Announcements

1. **Access Admin Interface**: Navigate to **Admin Section** → **Django Admin** (available at `/django-admin/`)
2. **Find Project Settings**: Go to the "Common" section and select "Project settings"
3. **Edit Announcement**: In the Project Settings form, locate the "Announcement" field
4. **Enter Message**: Type your announcement message. HTML formatting is supported for rich text display
5. **Save Changes**: Click "Save" to publish the announcement

### Announcement Display

- Announcements appear prominently on the main/home page
- All logged-in users will see the announcement when they access ADIT

#### Example Announcements

**Maintenance Notice:**

```html
<strong>Scheduled Maintenance:</strong> ADIT will be offline for maintenance on
<strong>March 15, 2024 from 2:00 AM to 4:00 AM UTC</strong>. Please plan your
transfers accordingly.
```

## ADIT Client

The [ADIT Client](https://pypi.org/project/adit-client/) is a Python library that accesses the DICOMweb API of ADIT. It can query (QIDO-RS), retrieve (WADO-RS, including the NIfTI resources) and store (STOW-RS) DICOM data on the servers the user has access to. It cannot create or manage selective, batch or mass transfer jobs; those are only available in the web interface.

**Basic Usage:**

```python
from adit_client import AditClient

# Initialize client
client = AditClient(server_url="https://adit.example.com", auth_token="your-api-token")

# Search for studies. The first parameter is the AE title of the DICOM server
# to query, the second a dictionary of DICOM query keys.
studies = client.search_for_studies("ORTHANC1", {"PatientID": "12345"})

# Retrieve all images of a study as pydicom datasets,
# optionally pseudonymized on the fly.
images = client.retrieve_study("ORTHANC1", studies[0].StudyInstanceUID, pseudonym="XFE3TEW2N")

# Store the images on another DICOM server
client.store_images("ORTHANC2", images)
```

To create an API token for programmatic access:

1. **Navigate** to **Token Authentication** by going to **"Profile"** --> **"Manage API Tokens"**
2. **Description** & **Expiry Time** : Add a description (optional) and expiry time for the token.
3. **Click** on **"Generate Token"**.
4. This token will only be visible once, so make sure to copy it now and store it in a safe place. As you will not be able to see it again, you will have to generate a new token if you lose it.

### Revoking Tokens

- **Admins** can revoke tokens by navigating to **Django Admin** --> **Token Authentication**
