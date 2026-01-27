# Admin Guide

The Admin Guide is intended for system administrators and technical staff responsible for configuring, and maintaining ADIT for DICOM data transfer.

## Installation

```terminal
Clone the repository: `git clone https://github.com/openradx/adit.git`
cd adit
uv sync
cp ./example.env ./.env  # copy example environment to .env
uv run cli stack-deploy  # builds and starts Docker containers for production (Docker Swarm)
```

## Updating ADIT

Follow these steps to safely update your ADIT:

1. **Verify no active jobs**: Navigate to Django Admin → **Jobs Overview** and confirm nothing is running
2. **Enable maintenance mode**: In Django Admin, navigate to **Common** → **Project Settings** and check the "Maintenance mode" checkbox, then save
3. Navigate to Production folder
4. **Backup database**: Run `uv run cli db-backup` to create a database backup
5. **Remove stack**: Run `uv run cli stack-rm` to remove all Docker containers and services
6. **Pull latest changes**: Run `git pull origin main` to fetch the latest code updates
7. **Update environment**: Compare `example.env` with your `.env` file and add any new environment variables or update changed values
8. **Pull Docker images**: Run `uv run cli compose-pull` to download the latest Docker images
9. **Deploy stack**: Run `uv run cli stack-deploy` to rebuild and start all services with the updated code
10. **Disable maintenance mode**: In Django Admin, navigate to **Common** → **Project Settings** and uncheck the "Maintenance mode" checkbox, then save

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

6. **Configure Group Access**: In the **DICOM node group accesses** section, specify which groups can use this server as source or destination

!!! note "DICOM Protocol Support"
To determine which DICOM protocols are supported by a server, consult the server's DICOM Conformance Statement.

### Folder Management

Administrators can configure upload folders and storage locations for DICOM files:

1. **Access Django Admin**: Navigate to **Django Admin** → **Admin Section**
2. **Configure Folders**: Go to **Core** → **DICOM Folders**
3. **Add or Edit Folder**:
   - Click **Add Folder** to create a new folder configuration
   - Enter a **Name** for the folder (e.g., "Research Uploads", "Clinical Archive")
   - Specify the **Path** where DICOM files should be stored
   - Set the **Quota**: Define the disk quota for this folder in GB
   - Configure **When to inform admin**: Set the threshold (as a percentage or absolute value) at which administrators should be notified about quota usage
4. **Assign to Groups**: Link folders to groups to control which users can access specific storage locations
5. **Save**: Click **Save** to apply changes

!!! tip "Quota Monitoring"
Administrators will receive notifications when folder usage reaches the configured threshold, allowing proactive storage management.

## Job Overview

The Admin section includes a **Job Overview** section where administrators can:

- Monitor real-time job status across all transfer operations
- View jobs by status: Pending, In Progress, Completed, Failed, or Cancelled
- Track job history

To access the Job Overview:

1. Navigate to **Admin Section** → **Job Overview**
2. Click on individual jobs for detailed information

### Broadcasting Messages

Administrators can send broadcast emails to all users:

1. Navigate to **Django Admin** → **Admin Section**
2. Look for the broadcast or messaging feature
3. Compose your message and send to all users

## System Announcements

System administrators can inform users about important updates, maintenance schedules, or system changes through the announcement feature.

### Creating Announcements

1. **Access Admin Interface**: Navigate to the Django admin interface (typically accessible at `/admin/`)
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

ADIT client could be used to access all the features of ADIT without using the web interface.

**Basic Usage:**

```python
from adit_client import AditClient

# Initialize client
client = AditClient(base_url="https://your-adit-server.com", token="your-api-token")

# Search for studies
studies = client.search_studies(patient_id="12345")

# Transfer studies
client.transfer_study(study_uid="1.2.3.4.5", destination="TARGET_AE")
```

To create an API token for programmatic access:

1. **Naviagte** to **Token Authentication** by going to **"Profile"** --> **"Manage API Token"**
2. **Description** & **Expiry Time** : Add a description (optional) and expiry time for the token.
3. **Click** on **"Generate Token"**.
4. This token will only be visible once, so make sure to copy it now and store it in a safe place. As you will not be able to see it again, you will have to generate a new token if you lose it.

### Revoking Tokens

- **Admins** can revoke tokens by navigating to **Django Admin** --> **Token Authentication**
