# ADIT

## About

ADIT (Automated DICOM Transfer) is a Swiss army knife to exchange DICOM data between various systems by using a convenient web frontend.

**Developed at**

<table>
  <tr>
    <td align="center"><a href="https://ccibonn.ai/"><img src="https://github.com/user-attachments/assets/adb95263-bc24-424b-b201-c68492965ebe" width="220" alt="CCI Bonn"/><br />CCIBonn.ai</a></td>
  </tr>
</table>

**in Partnership with**

<table>
  <tr>
    
  </tr>
  <tr>
    <td align="center"><a href="https://www.ukbonn.de/"><img src="https://github.com/user-attachments/assets/97a47dc2-5e9d-4903-ad4c-e79206dfb073" height="120" width="auto" alt="UK Bonn"/><br />Universitätsklinikum Bonn</a></td>
    <td align="center"><a href="https://www.thoraxklinik-heidelberg.de/"><img src="https://github.com/user-attachments/assets/1485b4c8-0749-4a5e-9574-759a3d819d1e" height="120" width="auto" alt="Thoraxklinik HD"/><br />Thoraxklinik Heidelberg</a></td>
  </tr>
  <tr>
    <td align="center"><a href="https://www.klinikum.uni-heidelberg.de/kliniken-institute/kliniken/diagnostische-und-interventionelle-radiologie/klinik-fuer-diagnostische-und-interventionelle-radiologie/"><img src="https://github.com/user-attachments/assets/6d7c402c-aeed-45db-a9dd-aad232128ef6" height="120" width="auto" alt="UK HD"/><br />Universitätsklinikum Heidelberg</a></td>
  </tr>
</table>

> [!IMPORTANT]
> ADIT is currently in early beta stage. While we are actively building and refining its features, users should anticipate ongoing updates and potential breaking changes as the platform evolves. We appreciate your understanding and welcome feedback to help us shape the future of ADIT.

## The Challenge: Traditional DICOM vs Modern Web Workflows

Many existing PACS servers, while robust, rely on older, specialized DICOM protocols (DIMSE) and often have web-based access (like DICOMweb) either not implemented or explicitly turned off for security reasons. This creates a significant hurdle for modern applications, especially those built for the web or requiring automated, scriptable access.

## How ADIT Bridges the Gap

ADIT acts as a **translation layer** between modern web APIs and traditional DICOM protocols:

```mermaid
sequenceDiagram
    participant Client as Your Script/App
    participant ADIT as ADIT Server
    participant Worker as ADIT Worker
    participant PACS as PACS Server

    Client->>ADIT: HTTP GET /dicomweb/studies?PatientAge=020-030&Modality=CT
    Note over ADIT: Receives DICOMweb/REST request

    ADIT->>Worker: Internal translation
    Note over Worker: Converts REST → DIMSE

    Worker->>PACS: C-FIND (DIMSE Protocol)
    PACS-->>Worker: DICOM Response

    Worker->>ADIT: Internal processing
    Note over ADIT: Converts DIMSE → REST

    ADIT-->>Client: HTTP 200 + JSON Response
```

## Features

- Transfer DICOM data between DICOM-compatible servers
- Download DICOM data to a specified folder
- Pseudonymize DICOM data on the fly
- Specify a trial name for the transferred data (stored in the DICOM header)
- Easy web interface to select which studies to transfer or download
- Upload a batch file to make multiple queries on a DICOM server
- Upload a batch file to transfer or download multiple studies
- A REST API and API client to manage transfers programmatically by an external script (see below)
- Define when transfers should happen (for example, more workers at night to reduce server load on a PACS)
- Fine-grained control of what users can or can't do and what they can access
- Help modals with detailed information for the most important features
- An upload portal to upload DICOM images through a web interface that can be pseudonymized on the client (before the transfer happens)

## API Client

[ADIT Client](https://github.com/openradx/adit-client) is a Python library to query, retrieve and upload DICOM images programmatically from a Python script. Thereby it can interact with DICOM (e.g. PACS) servers connected to an ADIT server.

## Screenshots

![Screenshot1](resources/screenshots/Screenshot_1.png)

![Screenshot2](resources/screenshots/Screenshot_2.png)

![Screenshot3](resources/screenshots/Screenshot_3.png)

![Screenshot4](resources/screenshots/Screenshot_3.png)

![Screenshot5](resources/screenshots/Screenshot_5.png)

## Disclaimer

ADIT is intended for research purposes only and is not a certified medical device. It should not be used for clinical diagnostics, treatment, or any medical applications. Use this software at your own risk. The developers and contributors are not liable for any outcomes resulting from its use.

## License

AGPL 3.0 or later
