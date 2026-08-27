# ADIT Client

## About

ADIT Client is the official Python client of [ADIT (Automated DICOM Transfer)](https://github.com/openradx/adit).
It wraps the DICOMweb API of an ADIT server (QIDO-RS, WADO-RS, STOW-RS and the NIfTI extension).
Transfer jobs (selective/batch transfer) are not managed through this client.

## Installation

Requires Python 3.12 or newer.

```bash
pip install adit-client
# or
uv add adit-client
```

## Usage

### Prerequisites

- Generate an API token in your ADIT profile.
- Make sure you have the permissions to access the ADIT API.
- Also make sure you have access to the DICOM nodes you want query.

### Code

```python
from adit_client import AditClient

server_url = "https://adit" # The host URL of the ADIT server
auth_token = "my_token" # The authentication token generated in your profile
client = AditClient(server_url=server_url, auth_token=auth_token)

# Search for studies. The first parameter is the AE title of the DICOM server
# you want to query.
studies = client.search_for_studies("ORTHANC1", {"PatientName": "Doe, John"})

# The client returns pydicom datasets.
study_descriptions = [study.StudyDescription for study in studies]
```

### Client options

`AditClient(server_url, auth_token, verify=True, trial_protocol_id=None, trial_protocol_name=None)`

- `verify`: `True`/`False` to enable/disable TLS verification, or the path to a CA bundle.
- `trial_protocol_id` / `trial_protocol_name`: sent along with every retrieve request so the
  server can set the corresponding DICOM tags on the retrieved data.

### Methods

Every method takes the AE title of the DICOM server as first argument.

Query (QIDO-RS), results are pydicom datasets:

- `search_for_studies(ae_title, query=None)`
- `search_for_series(ae_title, study_uid, query=None)`
- `search_for_images(ae_title, study_uid, series_uid, query=None)`

Retrieve (WADO-RS), the `retrieve_*` methods return lists of pydicom datasets, the `*_metadata`
methods return the DICOM JSON metadata and the `iter_*` methods stream the datasets one by one.
They accept an optional `pseudonym` that makes the server pseudonymize the data before sending it:

- `retrieve_study(ae_title, study_uid, pseudonym=None)`, `retrieve_study_metadata(...)`, `iter_study(...)`
- `retrieve_series(ae_title, study_uid, series_uid, pseudonym=None)`, `retrieve_series_metadata(...)`, `iter_series(...)`
- `retrieve_image(ae_title, study_uid, series_uid, image_uid, pseudonym=None)`, `retrieve_image_metadata(...)`

Store (STOW-RS):

- `store_images(ae_title, images)`: uploads a list of pydicom datasets.

NIfTI, returns `(filename, BytesIO)` tuples (the `iter_*` variants stream them):

- `retrieve_nifti_study(ae_title, study_uid)`, `iter_nifti_study(...)`
- `retrieve_nifti_series(ae_title, study_uid, series_uid)`, `iter_nifti_series(...)`
- `retrieve_nifti_image(ae_title, study_uid, series_uid, image_uid)`, `iter_nifti_image(...)`

## License

- AGPL 3.0 or later
