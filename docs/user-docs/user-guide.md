# User Guide

This guide will help you understand how to use **ADIT**

## How ADIT Works

ADIT acts as a bridge between different DICOM systems, enabling secure and controlled data transfer with built-in pseudonymization capabilities. ADIT solves this by acting as a "translator" that converts between web-friendly APIs and traditional DICOM protocols.

1. **You send** a simple web request (like getting data from any website) 2. **ADIT translates** your request into traditional DICOM commands 3. **ADIT communicates** with your PACS using its native protocols 4. **ADIT converts** the response back to web-friendly format 5. **You receive** easy-to-use JSON data or DICOM files.

This means your PACS can stay secure with its existing configuration, while you get modern web access through ADIT.

## Dashboard Overview

When you log into ADIT, you'll see the main dashboard with several sections:

- **Selective Transfers**: Search and select specific studies to transfer or download.
- **Batch Query**: Search for studies on a PACS server by using a batch file.
- **Batch Transfer**: Transfer or download multiple studies specified in a batch file.
- **DICOM Explorer**: Explore the DICOM data of a PACS server

## Main Workflows

### 1. Single Study Transfer

To transfer a single DICOM study:

1. Navigate to the "Selective Transfer" section
2. Select your source DICOM server
3. Enter search criteria (Patient ID, Study Date, etc.)
4. Browse and select the study you want to transfer
5. Choose your destination server
6. Configure transfer options (pseudonymization, trial name, etc.)
7. Start the transfer

### 2. Batch Operations

For transferring multiple studies:

1. Prepare a batch file
2. Go to "Batch Transfer" section
3. Upload your batch file
4. Review the detected studies
5. Configure global transfer settings
6. Start the batch transfer

### 3. Download Studies

To download DICOM studies to a local folder:

1. Search for the desired studies
2. Select "Download" instead of "Transfer"
3. Choose the download location
4. Start the download process

## User Interface Elements

### Search Filters

- **Patient ID**: Search by patient identifier
- **Patient Name**: Search by patient name
- **Study Date**: Filter by study date range
- **Modality**: Filter by imaging modality (CT, MRI, etc.)
- **Accession Number**: Search by accession number

### Transfer Options

- **Pseudonymization**: Enable/disable data anonymization
- **Trial Name**: Add a trial identifier to DICOM headers
- **Priority**: Set transfer priority level
- **Schedule**: Set when the transfer should occur

## Administrator Features

### System Announcements

System administrators can inform users about important updates, maintenance schedules, or system changes through the announcement feature.

#### Creating Announcements

1. **Access Admin Interface**: Navigate to the Django admin interface (typically accessible at `/admin/`)
2. **Find Project Settings**: Go to the "Common" section and select "Project settings"
3. **Edit Announcement**: In the Project Settings form, locate the "Announcement" field
4. **Enter Message**: Type your announcement message. HTML formatting is supported for rich text display
5. **Save Changes**: Click "Save" to publish the announcement

#### Announcement Display

- Announcements appear prominently on the main dashboard/home page
- All logged-in users will see the announcement when they access ADIT
- HTML content is rendered, allowing for formatted text, links, and styling
- Empty announcements are not displayed to users

#### Best Practices for Announcements

- **Keep messages concise**: Users should be able to quickly read and understand the message
- **Use clear language**: Avoid technical jargon when possible
- **Include timeframes**: For maintenance notifications, specify start and end times
- **Use appropriate formatting**: Utilize HTML tags like `<strong>`, `<em>`, or `<br>` for emphasis and structure
- **Update regularly**: Remove outdated announcements and keep information current

#### Example Announcements

**Maintenance Notice:**

```html
<strong>Scheduled Maintenance:</strong> ADIT will be offline for maintenance on
<strong>March 15, 2024 from 2:00 AM to 4:00 AM UTC</strong>. Please plan your
transfers accordingly.
```

**New Feature:**

```html
🎉 <strong>New Feature Available:</strong> Batch transfers now support
<em>automatic retry</em> for failed transfers.
<a href="/docs/features">Learn more</a>
```

**System Alert:**

```html
⚠️ <strong>Important:</strong> Due to increased usage, transfer speeds may be
temporarily reduced during peak hours (9 AM - 5 PM UTC).
```
