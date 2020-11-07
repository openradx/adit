[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/medihack/adit)

# About

ADIT (Automated DICOM Transfer) is a swiss army knife to exchange DICOM data between various systems.

# Features

-   Transfer DICOM data between DICOM / PACS servers
-   Download DICOM data to a network folder
-   Pseudonymize DICOM data on the fly
-   Specify a trial name for the transfered data (stored in the DICOM header)
-   Download the data to an encrpyted archive (7-Zip)
-   Use the web interface to select studies to transfer or download
-   Upload a batch file to transfer or download multiple studies
-   A continuous mode to transfer past and future studies automatically
-   Define when transfers should happen (to reduce PACS server load)
-   Find Patient IDs using the patient's name and birth date
-   Check if a list of studies is present on a DICOM server

# TODO

-   approval from an ethics committee
-   Evaluate to use diffhtml instead of morphdom, see https://diffhtml.org/api.html#inner-html
-   https://channels.readthedocs.io/en/stable/tutorial/part_1.html
-   Maybe another alternative is https://github.com/Polymer/lit-html
-   Exclude SR
-   Check why archive feature does not work correctly
-   Think about moving all those dicts to dataclasses when passing around data
    -- Allow provide a regex of StudyDescription in CSV batch file
    -- Allow to specify many modalities per row in CSV file
-   Better scheduler (with day in week and times)
-   Continous Transfer
-   move date parsing part in parsers.py and consumers.py to date_util.py
-   https://stackoverflow.com/questions/14259852/how-to-identify-image-receive-in-c-store-as-result-of-a-c-move-query
-   https://www.yergler.net/2009/09/27/nested-formsets-with-django/

# Testing and coverage commands

-   Alle tests müssen jetzt auf dem Docker Container ausgeführt werden
    docker exec -it adit_dev_web_1 pytest
    ptw --runner 'pytest -s --testmon' # Watch only changed tests with pytest watch
    python manage.py test -v 2 app_name # Show print outputs during test
    coverage run --source=. -m pytest # Run coverage only
    coverage report # Show coverage report
    coverage annotate # Annotate files with coverage
    pystest --cov=. # Run Pytest and report coverage (in one command)
    find . -name "\*,cover" -type f -delete # Delete all cover files (from coverage annotate)

# Supervisor commands

supervisord # Start supervisor daemon
supervisorctl # Supervisor control shell
supervisorctl shutdown # Shut down supervisor daemon

# Django commands

python manage.py shell_plus --print-sql # Show all SQL statements (django_extensions required)
python .\manage.py startapp continuous_transfer .\adit\continuous_transfer # Folder must exist

# Docker comands

docker-compose -f "docker-compose.dev.yml" -p adit_dev exec web pytest # Run Pytest on web container
docker build . --target development -t adit_dev # Build a volume from our Dockerfile
docker run -v C:\Users\kaisc\Projects\adit:/src -it adit_dev /bin/bash # Run the built container with src folder mounted from host
docker ps -a --filter volume=vol_name # Find container that mounts volume
docker run -v=adit_web_data:/var/www/adit -it busybox /bin/sh # Start interactive shell with named volume mounted
docker run --rm -i -v=adit_web_data:/foo busybox find /foo # List files in named volume
docker-compose -f "docker-compose.dev.yml" -p adit_dev up -d --build
docker-compose -f "docker-compose.prod.yml" -p adit_prod up -d --build

# Production setup

-   Copy cert.pem and key.pem from N:\Dokumente\Projekte\ADIT_Server\ssl_certificate to /var/www/adit/ssl/
-   Restart apit_prod_web container
-   Add Synapse DICOM server (Uncheck "Patient root get support"!!!)

# Celery commands

-   celery -A adit purge -Q default,low
-   celery -A adit inspect scheduled

# Celery Manage Python API

-   python manage.py shell_plus
    from adit.celery import app
    i = app.control.inspect()
    i.scheduled()
    app.AsyncResult("task_id").state

# Ports in development

-   see .gitpod.yml file

# Planned fields for BatchTransferJob model

max_period_size = models.PositiveIntegerField(default=100)
enforced_break = models.PositiveIntegerField(default=2000)
interval_start_time = models.TimeField()
interval_end_time = models.TimeField()

# Resources

## supervisord

-   https://medium.com/@jayden.chua/use-supervisor-to-run-your-python-tests-13e91171d6d3

## Testing

-   https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django

# Knowledge

-   It is not possible to set an ENV variable using the Gitpod Dockerfile
-   In Gitpod ENV variables can only be set using the Gitpod settings
-   The PYTHONPATH environment variable can't be set in the Gitpod settings (it is always overwritten with a blank value)
-   What is ALLOWED_HOSTS? https://www.divio.com/blog/django-allowed-hosts-explained/
-   The SECRET_KEY should not start with a dollar sign (\$), django-environ has problems with it (see Proxy value in the documentation)
-   Multi table inheritance extensions: https://github.com/django-polymorphic/django-polymorphic and https://github.com/jazzband/django-model-utils

# ContinousTransferJob

-   Fields: job_name, from, till (optional), dicom_tag_regex

# Big refactoring

job_type -> transfer_type
selectivetransferjob -> ---
batchtransferjob -> ---
job_type -> ?

# Make related fields work with InheritanceManager of django-model-utils.

# This unfortunately does not work for prefetching related fields with

# select_related (but does work for prefetch_related).

# Solution from https://github.com/jazzband/django-model-utils/issues/11

from django.db.models.fields.related_descriptors import ForwardManyToOneDescriptor

class InheritanceForwardManyToOneDescriptor(ForwardManyToOneDescriptor):
def get_queryset(self, \*\*hints):
return self.field.remote_field.model.objects.db_manager(
hints=hints
).select_subclasses()

class InheritanceForeignKey(models.ForeignKey):
forward_related_accessor_class = InheritanceForwardManyToOneDescriptor

# Warn (by sending an Email to the admins) when free disk space of

# a destination folder is below a defined size (in bytes). When set

# to None then no warning Email is sent.
