# About

ADIT (Automated DICOM Transfer) is a swiss army knife to exchange DICOM data between various systems by using a convenient web frontend.

# Features

- Transfer DICOM data between DICOM / PACS servers
- Download DICOM data to a local or network folder
- Pseudonymize DICOM data on the fly
- Specify a trial name for the transfered data (stored in the DICOM header)
- Use the web interface to select studies to transfer or download (Selective Transfer)
- Download the data to an encrpyted 7-Zip archive (only in Selective Transfer mode)
- Upload a batch file to make multiple queries on a DICOM server (Batch Query)
- Upload a batch file to transfer or download multiple studies (Batch Transfer)
- Define when transfers should happen, e.g. on at night (to reduce PACS server load)
- Fine-grained control of what users can do or can't do
- Help modals with detailed information for the most important features

# Upcoming features

- A REST API to manage transfers programmatically from a third party program.

# Screenshots

![Screenshot1](https://user-images.githubusercontent.com/120626/155511207-d3bdf595-d3ec-4dfb-a606-660b7b30fa5b.png)

![Screenshot2](https://user-images.githubusercontent.com/120626/155511254-95adbed7-ef2e-44bd-aa3b-6e055be527a5.png)

![Screenshot3](https://user-images.githubusercontent.com/120626/155511300-4dafe29f-748f-4d69-81af-89afe63197a0.png)

![Screenshot4](https://user-images.githubusercontent.com/120626/155511342-e64cd37d-4e92-4a9a-bbb0-4e88ea136d3c.png)

# Architectural overview

The backend of ADIT is built using the Django web framework and data is stored in a PostgreSQL database. For DICOM transfer pynetdicom of the pydicom project is used. The frontend is progressively enhanced with Javascript, but also works without it.

A transfer job contains one or more transfer tasks that describe what DICOM data to transfer and how to transfer it (source, destination, pseudonym, and so on).
A transfer task is processed by a Celery worker (a task scheduler) in the background running in its own Docker container. Celery internally uses RabbitMQ to send new tasks to the worker and Redis to store the results (if needed).

Redis is also used as a caching layer to relieve the PACS server of already done queries (e.g. querying for the Patient ID by using Patient Name and Patient Birth Date).

When the DICOM data to transfer needs to be modified (e.g. pseudonymized) it is downloaded temporarily to the ADIT webserver, then transformed and uploaded to the destination server resp. moved to the destination folder.

Downloading data from a DICOM server can done by using a C-GET or C-MOVE operation. C-GET is prioritized as a worker can fetch the DICOM data directly from the server. Unfortunately, C-GET is not supported by many DICOM servers. When downloading data using a C-MOVE operation, ADIT commands the source DICOM server to send the data to a C-STORE SCP server running in a separate container (named Receiver) that receives the DICOM data and sends it back to the worker using a RabbitMQ message.

# Contributors

[![](https://github.com/medihack.png?size=50)](https://github.com/medihack)
[![](https://github.com/mdebic.png?size=50)](https://github.com/mdebic)

# License

- GPLv3
