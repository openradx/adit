# About

ADIT (Automated DICOM Transfer) is a swiss army knife to exchange DICOM data between various systems.

# Features

-   Transfer DICOM data between DICOM / PACS servers
-   Download DICOM data to a network folder
-   Pseudonymize DICOM data on the fly
-   Specify a trial name for the transfered data (stored in the DICOM header)
-   Use the web interface to select studies to transfer or download (Selective Transfer)
-   Upload a batch file to transfer or download multiple studies (Batch Transfer)
-   Download the data to an encrpyted 7-Zip archive (only in Selective Transfer mode)
-   Define when transfers should happen (to reduce PACS server load)
-   A continuous mode to transfer past and future studies automatically (Continuous Transfer) [TBA]
-   Check if a list of studies is present on a DICOM server [TBA]

# Architectural overview

The frontend of ADIT is built using the Django web framework and data is stored in a PostgreSQL database. The frontend is fully functional without Javascript, but is progressively enhanced with Javascript.

A transfer job contains one or more transfer tasks that describe what DICOM data to transfer and how to transfer it (source, destination, pseudonymized, and so on).
A transfer task is processed by a Celery worker (a task scheduler) in the background running in its own Docker container.
Celery internally uses RabbitMQ to send new tasks to the worker and Redis to store the results (if needed).

Redis is also used as a caching layer to relieve the PACS server of already done queries (e.g. querying for the Patient ID by using Patient Name and Patient Birth Date).

When the DICOM data to transfer needs to be modified (e.g. pseudonymized) it is downloaded temporarily to the ADIT webserver, then transformed and uploaded to the destination server resp. moved to the destination folder.

DICOM data that does not need to be modified can be directly transferred between the source and destination server. The only exception is when source and destination server are the same, then the data will still be downloaded and uploaded again. This may be helpful when the PACS server treats the data somehow differently when sent by ADIT.

Downloading data from a DICOM server can done by using a C-GET or C-MOVE operation. C-GET is prioritized as a worker can fetch the DICOM data directly from the server. Unfortunately, C-GET is not supported by many DICOM servers. When downloading data using a C-MOVE operation, ADIT commands the DICOM server to send the data to DICOM C-STORE SCP server (named Receiver) that receives the DICOM data and sends it back to the worker using a RabbitMQ message.

# TODO list

-   Fix version of docker base containers (Postgres, Rabbit, ...)
-   Evaluate to use diffhtml instead of morphdom, see https://diffhtml.org/api.html#inner-html
-   Better scheduler (with day in week and times)

# Maybe features

-   Allow provide a regex of StudyDescription in CSV batch file
-   Allow to specify many modalities per row in CSV file
-   Continous Transfer
-   move date parsing part in parsers.py and consumers.py to date_util.py
-   https://stackoverflow.com/questions/14259852/how-to-identify-image-receive-in-c-store-as-result-of-a-c-move-query
-   https://www.yergler.net/2009/09/27/nested-formsets-with-django/
-   Allow to search multiple source servers with one query

# Commands

## Testing and coverage commands

-   docker exec -it adit_dev_web_1 pytest
-   ptw --runner 'pytest -s --testmon' # Watch only changed tests with pytest watch
-   python manage.py test -v 2 app_name # Show print outputs during test
-   coverage run --source=. -m pytest # Run coverage only
-   coverage report # Show coverage report
-   coverage annotate # Annotate files with coverage
-   pytest --cov=. # Run Pytest and report coverage (in one command)
-   find . -name "\*,cover" -type f -delete # Delete all cover files (from coverage annotate)

## Django commands

-   python manage.py shell_plus --print-sql # Show all SQL statements (django_extensions required)
-   python .\manage.py startapp continuous_transfer .\adit\continuous_transfer # Folder must exist

## Docker comands

-   docker-compose -f "docker-compose.dev.yml" -p adit_dev exec web pytest # Run Pytest on web container
-   docker-compose -f "docker-compose.dev.yml" -p adit_dev exec web pytest --cov=./adit # Run Pytest with coverage report
-   docker build . --target development -t adit_dev # Build a volume from our Dockerfile
-   docker run -v C:\Users\kaisc\Projects\adit:/src -it adit_dev /bin/bash # Run the built container with src folder mounted from host
-   docker ps -a --filter volume=vol_name # Find container that mounts volume
-   docker run -v=adit_web_data:/var/www/adit -it busybox /bin/sh # Start interactive shell with named volume mounted
-   docker run --rm -i -v=adit_web_data:/foo busybox find /foo # List files in named volume
-   docker-compose -f "docker-compose.dev.yml" -p adit_dev up -d --build
-   docker-compose -f "docker-compose.prod.yml" -p adit_prod up -d --build

## Celery commands

-   celery -A adit purge -Q default,low
-   celery -A adit inspect scheduled

# Deployment for production

-   Copy cert.pem and key.pem from N:\Dokumente\Projekte\ADIT_Server\ssl_certificate to /var/www/adit/ssl/
-   Restart apit_prod_web container
-   Add Synapse DICOM server (Uncheck "Patient root get support"!!!)
