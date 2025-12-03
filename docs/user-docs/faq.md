# Frequently Asked Questions (FAQ)

This section addresses common questions and troubleshooting issues when using ADIT.

## General Questions

### What is ADIT and why would I use it?

**Q: What does ADIT do exactly?**

A: ADIT (Automated DICOM Transfer) acts as a bridge between traditional DICOM systems and modern web applications. It allows you to:

- Transfer DICOM data between different PACS systems
- Access DICOM data through modern web APIs
- Pseudonymize patient data during transfers
- Automate batch operations for research workflows
- Provide secure, controlled access to medical imaging data

**Q: How is ADIT different from other DICOM tools?**

A: ADIT focuses on being a translation layer that:

- Works with existing PACS systems without requiring changes
- Provides modern web APIs while maintaining traditional DICOM security
- Offers user-friendly web interfaces for non-technical users
- Supports both manual and automated workflows

**Q: What DICOM protocols does ADIT support?**

A: ADIT supports the core DICOM networking protocols:

- **C-FIND**: Query DICOM servers for studies, series, and images
- **C-MOVE**: Request DICOM data transfer from servers (requires intermediate storage)
- **C-GET**: Direct retrieval of DICOM data from servers
- **C-STORE**: Send DICOM data to destination servers
- **DICOMweb**: QIDO-RS for queries and STOW-RS for storage (via DICOMweb API)

These protocols enable ADIT to connect to most PACS, VNA systems, and research databases.

## Installation & Setup

### Getting Started

**Q: How do I install ADIT?**

A: The easiest way is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/openradx/adit.git
cd adit

# Copy environment file and configure
cp example.env .env
# Edit .env with your settings

# Start ADIT
cli compose-up
```

**Q: How do I create the first admin user?**

A: There are two ways to create the first admin user:

**Option 1: Automatic creation (recommended)**
When you copy the example environment file, a default admin user can be created automatically:

```bash
cp example.env .env
# Edit .env and ensure the superuser environment variables are set
# Then start ADIT - the admin user will be created automatically
cli compose-up
```

**Option 2: Manual creation**
After starting ADIT, create a superuser manually:

```bash
# using the CLI tool
cli create-superuser
```

## Server Configuration

### Adding DICOM Servers

**Q: How do I add a DICOM server to ADIT?**

A: Via the Django admin interface:

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

**Q: How do I test if a server connection works?**

A: ADIT provides several ways to verify server connectivity:

1. Use the **DICOM Explorer** to try querying the server - if it can retrieve data, the connection works.
2. Try performing a selective transfer - connection issues will be reported in the job status

## User Management

### Permissions & Access

**Q: How does ADIT handle user permissions?**

A: ADIT uses a group-based permission system:

- **Groups** define access to specific DICOM servers through source/destination permissions
- **Users** are assigned to one or more groups

**Q: How do I configure user permissions in the web interface?**

A: Use the Django admin interface to manage groups and permissions:

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

### Authentication & Security

**Q: What authentication methods does ADIT support?**

A: ADIT supports the following authentication methods:

- **Django built-in authentication**: Username/password with session-based login for web interface
- **Token authentication**: For REST API access (tokens managed through web interface)
- **Group-based permissions**: Users must be assigned to groups to access DICOM servers
- **Admin approval**: New user registrations require administrator approval

## Transfer Operations

### Basic Transfers

**Q: How do I transfer a single study?**

A: Using Selective Transfer:

1. Go to **Selective Transfer**
2. Choose your **source server**
3. Search for studies using patient ID, date range, modality, etc.
4. Select the **study** you want to transfer
5. Choose the **destination server**
6. Configure options (pseudonym, trial info)
7. Optional: Covert it into NIfTI.
8. Optional: Send email after job completion.
9. **Start Transfer**

**Q: How do I monitor transfer progress?**

A: ADIT provides multiple ways to monitor transfer progress:

- **Previous Jobs**: Click on **Previous Jobs** in the main navigation to see all your transfer jobs and their current status
- **Admin Section**: Go to **Admin Section** → **Job Overview** for a comprehensive view of all system jobs
- Click on any specific job to see detailed progress and individual task status
- **Real-time Updates**: WebSocket connections provide live status updates on job detail pages
- **Email Notifications**: Can be enabled during job creation for completion alerts

### Batch Operations

**Q: How do I transfer multiple studies at once?**

A: Using Batch Transfer:

1. Prepare a **CSV or Excel file** with study details
2. Required columns: `PatientID`, `StudyInstanceUID`, `Destination`, `Pseudonym`, `SeriesInstanceUIDs`, `TrialProtocolID`
3. Go to **Batch Transfer** and upload your file
4. Review the detected studies and start the batch job

**Q: What's the format for batch files?**

A: Example CSV format:

```csv
PatientID,StudyInstanceUID,Destination,Pseudonym,TrialProtocolID
12345,1.2.3.4.5.6.7.8.9,ResearchPACS,SUBJ001,TRIAL2024
67890,1.2.3.4.5.6.7.8.10,ResearchPACS,SUBJ002,TRIAL2024
```

**Q: How do I handle batch transfer errors?**

A: ADIT provides detailed error reporting through its job monitoring interface:

- **Job Overview Table**: Shows columns for Job ID, Status, Message, Created at (timestamp), and Owner
- **Job Detail Pages**: Click on any Job ID to see comprehensive information about that specific transfer job
- **Task-level Details**: Within each job, view the status of individual transfer tasks
- **Error Messages**: Specific failure reasons are displayed for each failed task

## Pseudonymization

### Privacy Protection

**Q: How does pseudonymization work in ADIT?**

A: ADIT uses the dicognito library to:

- **Remove identifying information** from DICOM headers
- **Replace patient names/IDs** with provided pseudonyms
- **Add trial information** if specified
- **Maintain consistency** across multiple studies for the same patient

**Q: What DICOM tags are anonymized?**

A: ADIT anonymizes standard identifying tags including:

- Patient Name, Patient ID, Patient Birth Date
- Referring Physician, Institution Name
- Study Date, Study Description (optionally)
- Other tags according to DICOM anonymization profiles

**Q: Can I transfer data without pseudonymization?**

A: Yes, if you have the `can_transfer_unpseudonymized` permission:

1. Leave the **Pseudonym** field empty during transfer
2. The system will transfer original DICOM data unchanged
3. This requires special permission for privacy compliance

## API Usage

### DICOMweb API

**Q: How do I use ADIT's API programmatically?**

A: ADIT provides DICOMweb-compliant APIs with token-based authentication:

```python
import requests

# Get authentication token (must be created via web interface first)
auth_token = 'your_api_token_here'

# Query studies
response = requests.get(
    'https://adit.hospital.com/api/dicom-web/PACS1/qidors/studies',
    headers={'Authorization': f'Token {auth_token}'},
    params={
        'PatientID': '12345',
        'Modality': 'CT'
    }
)
studies = response.json()
```

**Note**: API tokens must be created through ADIT's web interface in the token authentication section.

**Q: How do I create an API token through the web interface?**

A: To create an API token for programmatic access:

1. **Log in** to ADIT with your user account
2. **Navigate to Adit Administration**:
   - Look for **Token Authentication** in the main navigation
3. **Generate New Token**:

   - Scroll down to the **"Generate New Token"** section
   - Choose an **Expiry Time** (1 Day, 7 Days, 30 Days, 90 Days, or Never if you have permission)
   - Optionally add a **Description** to identify the token's purpose
   - Click **"Generate Token"**

4. **Use the Token**: Include it in API requests as `Authorization: Token <your_token_here>`

## Troubleshooting

### Common Issues

**Q:Transfer fails with connection errors**

A: ADIT implements automatic retry logic for connection issues. Common connection error messages include:

- `"Could not connect to [server name]"` - Server unreachable or offline
- `"All sub-operations failed"` - Multiple retry attempts exhausted
- `"Connection failed, but will be retried"` - Temporary network issues

To troubleshoot connection failures:

1. **Check DICOM Explorer**: Use **DICOM Explorer** to test server connectivity - try querying the problematic server directly to verify it's reachable
2. **Admin access only**: DICOM server configuration (AE Title, host, port) can only be viewed/modified by administrators via **Django Admin** → **Dicom servers**
3.
4. **Server availability**: Contact the DICOM server administrator to confirm the server is running and accepting connections
5. **Review job details**: Click the **Job ID** in **Previous Jobs** to see specific error messages and retry attempts

**Note**: Regular users cannot view or modify DICOM server technical details like IP addresses or ports - this requires administrator access.

**Q:Batch upload fails with "Invalid Excel (.xlsx) file" error**

A: ADIT validates batch files strictly. Check:

1. **File format**: Must be a valid Excel (.xlsx) file, not CSV or older Excel formats
2. **Required columns**:
   - **Batch Transfer**: `PatientID` and `StudyInstanceUID` are required
   - **Batch Query**: Either `PatientID` OR (`PatientName` + `PatientBirthDate`) required
3. **File size**: Maximum upload size is 5MB (5242880 bytes exactly)
4. **Batch size limits**: Maximum 500 tasks per batch transfer job and 1000 tasks per batch query job (unless you're staff)
5. **Column headers**: First row must contain exact column names (case-sensitive)

**Q:Batch upload fails with validation errors**

A: ADIT performs content validation on batch files:

1. **Data format**: Patient IDs, Study UIDs must match DICOM format requirements
2. **Permission check**: Pseudonym field required unless you have `can_transfer_unpseudonymized` permission
3. **Consistency**: Same Study UID cannot belong to different Patient IDs
4. **Character validation**: No backslashes, control characters, or wildcards in ID fields

**Q:Jobs get stuck or fail with timeout errors**

A: ADIT has built-in timeout and retry mechanisms.

1. **Connection retries**: Network connections automatically retry twice with 30-second delays between attempts
2. **Task retries**: Failed tasks retry up to 3 times with exponential backoff intervals
3. **Individual task timeout**: Tasks timeout after 20 minutes of execution
4. **DIMSE operation timeout**: DICOM network operations timeout after 60 seconds by default
5. **Check job status**: Click on a **Job ID** in the **Previous Jobs** list to view detailed progress, error messages, and retry information

### Getting Help

**Q: Where can I get more help?**

A: Support resources:

- **Documentation**: Check the [user guide](user-guide.md), [technical overview](../technical-overview.md)
- **GitHub Issues**: Report bugs or request features on [GitHub](https://github.com/openradx/adit/issues)
- **Logs**: Check ADIT logs for detailed error information

**Q: How do I report a bug?**

A: When reporting issues, please include:

1. **Steps to reproduce** the problem
2. **Error messages** from the UI or logs
3. **DICOM server types** you're connecting to

**Q: How can I contribute to ADIT?**

A: Contributions are welcome!

- Check the [contributing guide](../dev-docs/contributing.md)
- Look for issues labeled "good first issue" on GitHub
- Submit feature requests or bug reports
- Contribute to documentation improvements
