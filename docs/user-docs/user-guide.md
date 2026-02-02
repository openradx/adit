# User Guide

The User Guide is designed for end users who interact with ADIT to perform DICOM data transfers. It explains how to use the application’s features, and execute common workflows in a clear and practical manner.

## Functionalities Overview

When you log into ADIT, you'll see the home page with several sections:

- **Selective Transfers**: Search and select specific studies to transfer or download.
- **Batch Query**: Search for studies on a PACS server by using a batch file.
- **Batch Transfer**: Transfer or download multiple studies specified in a batch file.
- **DICOM Explorer**: Explore the DICOM data of a PACS server
- **DICOM Upload**: Upload DICOM files from your local system to a PACS server

### 1. Selective Transfer

To transfer a single DICOM study:

1. Navigate to the "Selective Transfer" section
2. Select your source DICOM server
3. Enter search criteria (Patient ID, Study Date, etc.)
4. Browse and select the study you want to transfer
5. Choose your destination server
6. Configure transfer options (pseudonymization, trial name, etc.)
7. Start the transfer

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

### 4. Download Studies

To download DICOM studies to a local folder:

1. Search for the desired studies
2. Select "Download" instead of "Transfer"
3. Choose the download location
4. Start the download process

### 5. Upload DICOM Files

To upload DICOM files to a PACS server:

1. Navigate to the "DICOM Upload" section
2. Select your destination DICOM server
3. Choose the DICOM files or folders to upload
4. Start the upload process
5. Monitor the upload progress and verify completion

### 6. Explore DICOM Data

To browse and explore DICOM data on a server:

1. Go to the "DICOM Explorer" section
2. Select the DICOM server to explore
3. Use the hierarchical navigation (Patient → Study → Series)
4. View DICOM metadata and image information

### 7. ADIT Client (Programmatic Access)

The **ADIT Client** is a Python package (`adit-client`) that provides programmatic API access to ADIT functionality. It enables automated DICOM operations through Python scripts and returns data as pydicom datasets for seamless integration into your workflows.

**Key Features:**

- Automate repetitive DICOM transfer tasks
- Integrate ADIT operations into existing Python applications
- Retrieve DICOM data as pydicom datasets for analysis
- Execute batch operations programmatically
- Access all ADIT features without using the web interface

**When to Use:**

- Automating regular transfer workflows
- Integrating DICOM transfers into data pipelines
- Processing large batches of studies programmatically
