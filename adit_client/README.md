# ADIT Client

## About

ADIT Client is the official Python client of [ADIT (Automated DICOM Transfer)](https://github.com/openradx/adit).

## Usage

### Prerequisites

- Generate an API token in your ADIT profile.
- Make sure to have the permissions to access the ADIT API.
- Also make sure you have access to the DICOM nodes you want query.

### Code

```python
server_url = "https://adit" # The host URL of the ADIT server
auth_token = "my_token" # The authentication token generated in your profile
client = AditClient(server_url=adit_url, auth_token=adit_token)

# Search for studies
studies = client.search_for_studies("ORTHANC1", {"PatientName": "Doe, John"})

# The client returns pydicom datasets
study_descriptions = [study.StudyDescription for study in studies]
```
