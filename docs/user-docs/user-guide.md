# User Guide

The User Guide is designed for end users who interact with ADIT to perform DICOM data transfers. It explains how to use the application’s features, and execute common workflows in a clear and practical manner.

## Functionalities Overview

When you log into ADIT, you'll see the home page with several sections:

- **Selective Transfer**: Search and select specific studies to transfer or download.
- **Batch Query**: Search for studies on a PACS server by using a batch file.
- **Batch Transfer**: Transfer or download multiple studies specified in a batch file.
- **Mass Transfer**: Transfer large volumes of imaging data over a time range using reusable filters.
- **DICOM Explorer**: Explore the DICOM data of a PACS server.

**DICOM Upload** (upload DICOM files from your local system to a PACS server) is available from the navigation bar.

## Managing Jobs and Tasks

All operations in ADIT (selective transfers, batch queries, batch transfers, mass transfers) follow a **Job → Task** pattern. A job contains one or more tasks, and each task processes a single unit of work (e.g. one study transfer or one query). Both jobs and tasks have a status that reflects their current state.

### Job and Task Statuses

**Job statuses**: `Unverified`, `Pending`, `In Progress`, `Canceling`, `Canceled`, `Success`, `Warning`, `Failure`

**Task statuses**: `Pending`, `In Progress`, `Canceled`, `Success`, `Warning`, `Failure`

The job status is automatically derived from the status of its tasks. If any task is still pending, the job is pending (unless it is being canceled). If any task is in progress, the job is in progress (or canceling). Once all tasks are finished, the job status reflects the overall outcome (success, warning, failure, or canceled).

### Job Actions

Staff users can act on any job. Regular users can only act on their own jobs.

| Action | Available when | Who can use | What it does |
|---|---|---|---|
| **Verify** | `Unverified` | Staff only | Approves the job, sets it to `Pending`, and queues all tasks for processing |
| **Delete** | `Unverified` or `Pending` (with no tasks already started) | Owner or staff | Permanently deletes the job and all its tasks |
| **Cancel** | `Pending` or `In Progress` | Owner or staff | Stops the job. Pending tasks are canceled immediately. In-progress tasks are aborted |
| **Resume** | `Canceled` | Owner or staff | Resumes a canceled job by re-queuing all canceled tasks |
| **Retry** | `Failure` | Owner or staff | Re-queues only the failed tasks. Successful and warning tasks are left untouched |
| **Restart** | `Canceled`, `Success`, `Warning`, or `Failure` | Staff only | Resets and re-queues all tasks, starting the entire job from scratch |

### Task Actions

Staff users can act on any task. Regular users can only act on tasks belonging to their own jobs.

| Action | Available when | Who can use | What it does |
|---|---|---|---|
| **Delete** | `Pending` | Owner or staff | Permanently deletes the task |
| **Reset** | `Canceled`, `Success`, `Warning`, or `Failure` | Owner or staff | Resets the task to `Pending` and re-queues it for processing. The job status updates accordingly |
| **Kill** | `In Progress` | Staff only | Forcefully stops a running task |

---

## Functionalities

### 1. Selective Transfer

To transfer a single DICOM study:

1. Navigate to the "Selective Transfer" section
2. Select your source DICOM server
3. Enter search criteria (Patient ID, Study Date, etc.)
4. Browse and select the study you want to transfer
5. Choose your destination server
6. Configure transfer options (pseudonymization, trial name, etc.)
7. Start the transfer

**Options**: Besides the **Pseudonym**, the form offers a **Trial ID** and **Trial name** (stored in the DICOM header of the transferred data), **Urgent** (prioritizes the job; only shown with the "Can process urgently" permission) and **Send Email when job is finished**. When the destination is a folder, you can additionally set an **Archive password** to protect the downloaded archive and enable **Convert to NIfTI** to convert the downloaded series to NIfTI format.

### 2. Batch Query

With a Batch Query you can create a job to find data of multiple studies in a source DICOM / PACS server. Batch query jobs are put into a queue and will be processed by a worker when the time is right. You will get an Email when the job is finished (or failed for some reason).

Each batch query job contains several query tasks that define what studies to search for. The search terms must be specified in an Excel file (.xlsx). The first row of the Excel file must contain the header with the column titles (see below). Each of the following rows represent a query task.

!!! warning "Excel Data Format"
    If PatientID or AccessionNumber contains leading zeros those are relevant as it is not a number but a text identifier. So make sure that your Excel file does not remove those leading zeros by setting the column type to text or add a single quote `'` as prefix to the text cell itself.

These are the columns in the batch file to execute your queries:

- **PatientID**: The unique ID of the patient in the PACS.
- **PatientName**: The name of the patient.
- **PatientBirthDate**: The birth date of the patient.
- **AccessionNumber**: The Accession Number (a unique ID) of the study.
- **From**: Only include studies newer than or equal to this date.
- **Until**: Only include studies older than or equal to this date.
- **Modality**: The modality of the study. Multiple modalities to query can be provided as a comma separated list.
- **StudyDescription**: Only include studies with a matching study description. The value is sent to the PACS as a DICOM query attribute, so the DICOM wildcards `*` and `?` can be used.
- **SeriesDescription**: Only include series of the study, whose series description match a certain case insensitive regular expression pattern (see introduction into using a regular expression and testing your regular expression).
- **SeriesNumber**: Only include series of the study with the specified series number. Multiple series numbers can be provided as a comma separated list.
- **Pseudonym**: A pseudonym to pseudonymize the images during a subsequent transfer with Batch Transfer.

The patient must be identifiable by either "PatientID" or "PatientName" together with "PatientBirthDate". The remaining fields are optional and may limit the results for what you really need.

### 3. Batch Transfer

With this form you can create a new batch transfer job to transfer studies from a source server to a destination. Batch transfer jobs are put into a queue and will be processed by a worker when the time is right. You will get an Email when the job is finished (or failed for some reason).

Each batch transfer job contains several transfer tasks that define what studies to transfer. This data must be specified in an Excel file (.xlsx). The first row of the Excel file must contain the header with the column titles. The following rows contain the data that identifies the studies to transfer.

The required PatientID and StudyInstanceUID can be fetched by doing a "Batch Query". The resulting file of a batch query can be used for the batch transfer. So a batch query is usually a preparation step for a batch transfer.

!!! warning "Excel Data Format"
    If PatientID or AccessionNumber contains leading zeros those are relevant as it is not a number but a text identifier. So make sure that your Excel file does not remove those leading zeros by setting the column type to text or add a single quote `'` as prefix to the text cell itself.

The following columns must be defined in the batch file:

- **PatientID**: The unique ID of the patient in the PACS. This column is required.
- **StudyInstanceUID**: A unique ID that identifies the study. This column is required.
- **SeriesInstanceUID**: An unique ID that identifies the series. This column is optional to only transfer specific series of a study.
- **Pseudonym**: A pseudonym to pseudonymize the images during transfer. This field is required if you don't have the permission to transfer unpseudonymized (the default).

The "SeriesInstanceUID" is optional. If provided, only the specified series of the study will be transferred. The provided pseudonym is optional if you have the permissions to transfer unpseudonymized. It will be set as PatientID and PatientName. So it is recommended to use cryptic identifier strings (e.g. "XFE3TEW2N").

### 4. Mass Transfer

A mass transfer job transfers all series that match a set of filters within a date range from a source DICOM server to a destination (a DICOM server or a folder). It is intended for large volumes of data, e.g. to build a dataset for a study. Creating mass transfer jobs requires the "Can add mass transfer job" permission. Like all other jobs, a mass transfer job is put into a queue and processed by the mass transfer workers. You will get an Email when the job is finished if you enable it in the form.

The **Transfer scope** of the form has the following fields:

- **Source**: The DICOM server to search and fetch from.
- **Destination**: A DICOM server or a folder.
- **Start date** / **End date**: The study date range to cover.
- **Partition granularity**: The date range is split into **Daily** or **Weekly** partitions. Each partition becomes one task of the job, so partitions are processed in parallel and can be retried individually.
- **Pseudonymize**: Enabled by default. Pseudonyms are derived from the patient ID and the **Pseudonym salt**. Keep the pre-filled salt so that the same patient gets the same pseudonym within the job. Reuse the salt of a previous job (by pasting it) to keep pseudonyms consistent across jobs. Leave the salt blank to pseudonymize each study independently without an association between patient IDs and pseudonyms.
- **Trial ID** / **Trial name**: Stored in the DICOM header of the transferred data.
- **Convert to NIfTI**: Only available when the destination is a folder. Exported series are converted to NIfTI format using dcm2niix. Series of the modalities SR, KO and PR cannot be converted and are skipped.
- **Send Email when job is finished**

The **Filters (JSON)** field takes a JSON array of filter objects. Each filter object can contain the following keys:

- `mode`: `"include"` (default) or `"exclude"`.
- `modality`
- `institution_name` and `apply_institution_on_study`: Whether the institution is matched on study level (default `true`). Ignored on exclude filters, which always match the institution on series level.
- `study_description`
- `series_description`
- `series_number`
- `min_age` and `max_age`: Patient age range in years.
- `min_number_of_series_related_instances`: Minimum number of images in a series.

A series matching ANY include filter is included, then any series also matching an exclude filter is removed. At least one include filter is required. String criteria support the DICOM wildcards `*` and `?` and are matched against the whole value. Include filters are sent to the PACS and matched case-sensitively (as a standard-conformant PACS matches non-name fields in C-FIND). Exclude filters are applied by ADIT to the retrieved results and matched case-insensitively, so e.g. `*cor*` also removes series described as `COR` or `Cor`.

Example:

```json
[
  {
    "mode": "include",
    "modality": "MR",
    "institution_name": "Neuroradiologie",
    "apply_institution_on_study": true,
    "min_age": 18,
    "max_age": 90
  },
  {
    "mode": "exclude",
    "series_description": "localizer"
  }
]
```

Each series found by the job is tracked as a volume with one of the statuses `Pending`, `Exported`, `Converted` (to NIfTI), `Skipped` or `Error`. The volumes of a partition are listed on the task page together with a log for skipped and failed ones. On the job page, **Export CSV** downloads a list of all volumes of the job with the partition, pseudonym, patient ID, accession number, original and pseudonymized study and series UIDs, modality, study and series description, series number, study date and time, institution and number of images. When pseudonymization is enabled, the pseudonym salt is written to the first line of the CSV file.

### 5. Download Studies

There are two ways to download DICOM data to a local folder:

- **Transfer to a folder**: In Selective Transfer and Batch Transfer, choose a DICOM folder as the destination instead of a server. Folders are network drives configured by an administrator; you only see the folders your groups have access to. The data is written to that folder. In Selective Transfer you can additionally set an **Archive password** and enable **Convert to NIfTI** for folder destinations.
- **Direct study download**: In the search results of Selective Transfer, each study has a download button that streams the study as a ZIP archive to your browser. The pseudonymization options of the form are applied to the download. The button is only shown to users with the "Can download study" permission.

### 6. Upload DICOM Files

Uploading requires the "Can upload data" permission. To upload DICOM files to a PACS server:

1. Navigate to "DICOM Upload" in the navigation bar
2. Enter a **Patient Pseudonym** (required). The uploaded data is always pseudonymized
3. Select your destination DICOM server
4. Choose the DICOM files or folders to upload
5. Start the upload process
6. Monitor the upload progress and verify completion

The files are pseudonymized in your browser before they are sent to ADIT, so unpseudonymized data never leaves your computer. The pseudonymization uses a seed configured on the ADIT server (`ANONYMIZATION_SEED`), so the same original identifiers result in the same pseudonymized values across uploads to the same ADIT instance.

### 7. Explore DICOM Data

To browse and explore DICOM data on a server:

1. Go to the "DICOM Explorer" section
2. Select the DICOM server to explore
3. Use the hierarchical navigation (Patient → Study → Series)
4. View DICOM metadata and image information

### 8. ADIT Client (Programmatic Access)

The **ADIT Client** is a Python package (`adit-client`) that accesses the DICOMweb API of ADIT from Python scripts. It returns data as pydicom datasets for seamless integration into your workflows.

**What it can do:**

- Query studies, series and images on a DICOM server (QIDO-RS)
- Retrieve studies, series and images, optionally pseudonymized on the fly (WADO-RS)
- Retrieve studies, series and images converted to NIfTI
- Store images on a DICOM server (STOW-RS)

The client only covers the DICOMweb API. Selective, batch and mass transfer jobs cannot be created or managed with it; use the web interface for those.

**When to Use:**

- Integrating DICOM queries and retrievals into data pipelines
- Fetching and processing studies programmatically, e.g. for analysis scripts

To use the client you need an API token, which you can generate in your profile under **Manage API Tokens**. See the [Admin Guide](admin-guide.md#adit-client) for a code example.
