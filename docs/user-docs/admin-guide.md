# Admin Guide

The Admin Guide is intended for system administrators and technical staff responsible for configuring, and maintaining ADIT for DICOM data transfer.

## Installation

On the server ADIT lives in a production folder (e.g. `adit_prod`) that holds the checkout and the `.env` file:

```terminal
git clone https://github.com/openradx/adit.git adit_prod
cd adit_prod
uv sync
cp ./example.env ./.env  # set ENVIRONMENT=production and adjust the variables (see below)
uv run cli compose-pull  # pulls the Docker image (ADIT_IMAGE, default ghcr.io/openradx/adit:latest)
uv run cli stack-deploy  # starts the Docker Swarm stack
```

### Environment Variables

All settings are read from `.env`; the comments in `example.env` describe every variable. For production at least set:

- `ENVIRONMENT=production`
- Secrets: `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, `TOKEN_AUTHENTICATION_SALT`, `SUPERUSER_PASSWORD`, `SUPERUSER_AUTH_TOKEN` (generate with `uv run cli generate-django-secret-key`, `generate-secure-password`, `generate-auth-token`)
- Hosts: `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `SITE_DOMAIN`
- DICOM: `CALLING_AE_TITLE`, `RECEIVER_AE_TITLE` (both required), `RECEIVER_PORT`
- SSL: `SSL_SERVER_CERT_FILE`, `SSL_SERVER_KEY_FILE`, `SSL_SERVER_CHAIN_FILE` (`uv run cli generate-certificate-chain` builds the chain from your CA-signed certificate)
- Email: `DJANGO_EMAIL_URL`, `DJANGO_SERVER_EMAIL`, `DJANGO_ADMIN_EMAIL`, `SUPPORT_EMAIL`
- Folders: `MOUNT_DIR` (download folders, see [Folder Management](#folder-management)), `BACKUP_DIR`
- `ANONYMIZATION_SEED` for the upload portal

Optional tuning: `WEB_REPLICAS`, `DICOM_WORKER_REPLICAS`, `MASS_TRANSFER_WORKER_REPLICAS` (service scaling), `EXCLUDE_MODALITIES` (modalities skipped in pseudonymized web transfers, default `PR,SR`), `BACKUP_CRON`, `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` and `DICOM_TASK_SWEEP_CRON` (see [Worker Crash Recovery](#worker-crash-recovery)), `ADIT_IMAGE` and `STACK_NAME` (a second stack such as staging on the same host), and `ROUTER_AE_TITLE`, `ROUTER_PORT` and `ROUTER_SPOOL_DIR` for the DICOM router (an empty `ROUTER_AE_TITLE` disables it; put the spool on an encrypted disk). The router is set up as described in [DICOM Router](#dicom-router); `ROUTER_QUIET_PERIOD_SECONDS`, `ROUTER_MAX_OPEN_SECONDS` and `ROUTER_FAILED_RETENTION_DAYS` tune how long studies wait in the spool.

!!! warning "No quotes in .env"
    Values must not be wrapped in quotes; Docker Swarm treats them as part of the value, and `stack-deploy` refuses to run when it finds any.

## Updating ADIT

1. **Verify no active jobs**: **Admin Section** → **Job Overview** (`/admin-section/`) shows nothing pending or in progress
2. **Enable maintenance mode**: In Django Admin, **Common** → **Project settings**, check "Maintenance" and save
3. **Navigate to the production folder** (e.g. `adit_prod`)
4. **Backup database**: `uv run cli db-backup`
5. **Remove stack**: `uv run cli stack-rm`
6. **Pull latest changes**: `git pull origin main`
7. **Update environment**: Compare `example.env` with your `.env` and add new or changed variables. Keep `STACK_NAME` unchanged, otherwise a second stack is deployed next to the old one
8. **Pull Docker images**: `uv run cli compose-pull`
9. **Deploy stack**: `uv run cli stack-deploy`
10. **Disable maintenance mode**: Uncheck "Maintenance" in **Project settings** and save

### Worker Crash Recovery

When a worker dies while a task is in progress, the task stays `In Progress` until a periodic sweep (every minute by default, `DICOM_TASK_SWEEP_CRON`; also at every worker start) puts it back to `Pending` once its worker has sent no heartbeat for `DICOM_TASK_STALLED_WORKER_GRACE_SECONDS` (30 s by default). No manual intervention is needed; a task that stays `In Progress` much longer than that means the worker is alive but blocked.

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

## DICOM Router

The DICOM router receives the studies a PACS forwards to it and sends the series that staff-defined routing rules select to other DICOM servers, optionally pseudonymized. For example, every CT head study of a patient aged 20 to 30 can be pseudonymized and sent to a research XNAT, filed under the right project. The `router` container only receives the images and stores them in a spool; the default worker checks the rules once no image of a study has arrived for `ROUTER_QUIET_PERIOD_SECONDS` (5 minutes by default), and the DICOM workers deliver.

### Setting Up the Router

1. **Choose an AE title**: Set `ROUTER_AE_TITLE` in `.env` (different from `RECEIVER_AE_TITLE`, for example `ADIT1ROUTER`) and, in production, the host port `ROUTER_PORT` (default 11113). Redeploy the stack. An empty `ROUTER_AE_TITLE` keeps the router off.
2. **Place the spool**: The spool is shared by the `router`, `default_worker` and `dicom_worker` containers. Like `MOUNT_DIR`, it assumes these containers run on one host or share a network filesystem. By default it is a Docker volume; `ROUTER_SPOOL_DIR` puts it in a host folder instead, which belongs on an encrypted disk (see [Router Security](#router-security)).
3. **Register the PACS as a sender** (see [Registering Senders](#registering-senders)).
4. **Configure forwarding on the PACS**: Add ADIT as a DICOM destination with the router's AE title, the ADIT host and `ROUTER_PORT`, and forward new studies to it. Keep the PACS's forwarding filter as narrow as your rules allow, for example CT only: everything the PACS forwards is received and checked, and studies no rule matches are only deleted again.

### Registering Senders

The router only accepts images from registered senders and rejects everyone else.

1. Make sure the PACS exists as a DICOM server (**Django Admin** → **Core** → **Dicom servers**)
2. Go to **Django Admin** → **Router** → **Router senders** and click **Add router sender**
3. Choose the PACS as **Server**. Leave **Calling AE title** empty to use the server's AE title, or enter the AE title the PACS sends from if it differs from the one it answers queries on
4. Save. Unchecking **Enabled** later makes the router refuse that sender

Senders are managed only in the Django admin. **Router** → **Router settings** → **Suspended** pauses receiving: the router answers every image with "out of resources", so the PACS keeps the images and sends them again later. Deliveries continue while the router is suspended.

### Writing Routing Rules

Routing rules are managed on the **Router** pages, which only staff users see in the main menu.

- **Router** lists every rule with its destination, whether it pseudonymizes, its deliveries by status and its last match. **New Rule** opens the rule form: a name, the destination (a DICOM server with C-STORE or STOW-RS support), the filters in the JSON format of mass transfer, pseudonymization and the trial protocol ID and name. The **Help** button of the form explains the filters.
- A series is sent when it matches at least one include filter and no exclude filter. A rule without series-level conditions (modality, series description, series number, minimum number of images) sends the whole study. Every matching rule sends its own copy, independently of the other rules.
- A rule's page shows its settings and deliveries and offers **Edit Rule**, **Disable Rule** (or **Enable Rule**) and **Retry Failed Deliveries**. A rule that has sent studies can't be deleted, only disabled. A changed rule applies to the studies checked afterwards; studies checked while a rule is disabled are not sent for it later.
- **Disable Rule** always works. **Enable Rule** first checks the rule: if it no longer validates, for example because its destination can't receive images any more, the rule stays disabled and the page names the problem. Fix it with **Edit Rule**.
- Once a rule has sent a study, **Pseudonymize** and the salt can't change any more, because a patient must keep the same pseudonym. Create a new rule instead.
- Creating a rule without pseudonymization, or switching it off, needs the permission `router | router job | Can transfer unpseudonymized`.
- A destination must never forward studies back to the router's AE title: the router would receive its own deliveries and send them again, in a loop.

### XNAT Projects

Set the rule's trial protocol ID to the XNAT project ID and keep pseudonymization on. The router then writes `Project:<trial protocol ID> Subject:<pseudonym> Session:<pseudonym>_<study date>-<study time>` into the Patient Comments of every image, and XNAT files the session under that project and subject. This text needs a pseudonym, so a rule without pseudonymization only sets the trial protocol attributes. A study whose images arrive with long pauses is delivered in several batches under the same pseudonym; XNAT merges them automatically only in projects that archive automatically.

### Presentation States and Structured Reports

`EXCLUDE_MODALITIES` does not apply to the router: as in mass transfer, only the rule's filters decide what is sent. A rule that sends whole studies also sends their presentation states (PR) and structured reports (SR). Leave them out with exclude filters:

```json
[
  {"mode": "include", "study_description": "*Head*", "min_age": 20, "max_age": 30},
  {"mode": "exclude", "modality": "PR"},
  {"mode": "exclude", "modality": "SR"}
]
```

### Sending Older Studies

The router only sees the studies the PACS forwards from now on. To send older studies (a backfill), create a mass transfer job over their date range with the rule's filters, pseudonymization on, the rule's salt (shown in the rule's edit form) and the same trial protocol ID. The same filters and salt give the same selection, pseudonyms and replacement UIDs, so the destination files the backfill together with the router's deliveries.

### Deliveries and Retention

For every study a rule matches, and for every follow-up batch of it, the router creates a router job with one delivery task, owned by the rule's creator. The jobs are listed on the rule's page and under **Router Jobs**, and the [Job Overview](#job-overview) counts them. A job can be canceled, retried, restarted and reset, and a running task killed, like other jobs; it can't be deleted, so canceling keeps its history. Images that arrive after a study was checked are sent as a follow-up batch with the same pseudonym. Images a rule sent before are not sent again for `ROUTER_SENT_LIST_RETENTION_DAYS` (30 days).

How long data stays in the spool:

- An open study waits until no image of it has arrived for `ROUTER_QUIET_PERIOD_SECONDS` (300), at most `ROUTER_MAX_OPEN_SECONDS` (3600) after its first image
- A study no rule matches is deleted right after the check
- A batch whose deliveries all succeeded (also with warnings) or were canceled is deleted at the next run of `close_router_batches` (`ROUTER_CLOSE_CRON`, every minute)
- A batch with a failed delivery is kept for `ROUTER_FAILED_RETENTION_DAYS` (7) after it closed, so the delivery can be retried; the admins get a daily mail with the failed deliveries and the date their images will be deleted. Afterwards Retry, Restart and Reset are refused, and the PACS has to forward the study again
- Unreadable files stay in quarantine for `ROUTER_QUARANTINE_RETENTION_DAYS` (7)

When the spool has less than `ROUTER_SPOOL_MIN_FREE_GB` (20) free, the router refuses new images (the PACS sends them again later) and mails the admins, at most every `ROUTER_LOW_SPACE_MAIL_HOURS` (6).

### Router Security

- Only the PACS network may reach the router port (`ROUTER_PORT`); block it for everyone else in the firewall.
- An AE title is not authentication. Anyone who can reach the port and knows a sender's AE title can send images, and the rules forward them.
- The spool holds identifiable images, so it belongs on an encrypted disk (`ROUTER_SPOOL_DIR`).
- A routing rule is a standing export of patient data, so only staff users can see and change rules and router jobs.

## Job Overview

The **Admin Section** (available at `/admin-section/` for staff users) includes a **Job Overview** table with one row per job type (Selective Transfer, Batch Query, Batch Transfer, Mass Transfer, Router) and one column per status: Unverified, Pending, In Progress, Canceling, Canceled, Success, Warning, Failure. Each cell shows the number of jobs and links to the filtered job list of all users, where you can open individual jobs for details.

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
