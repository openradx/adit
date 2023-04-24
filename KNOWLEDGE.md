# RESOURCES.md

## Django

### `null=True` and `blank=True`

- On text and char fields use `blank=True` alone (without `null=True`)
- On non string fields always use `blank=True` together with `null=True`
- If the string field is initially not set directly use with `default=""`
- See also <https://books.agiliq.com/projects/django-orm-cookbook/en/latest/null_vs_blank.html>

### FilterMixin does not work in DetailView

- DetailView queries the object in get_object() using the get_queryset()
- This collides with FilterMixin as it also gets its data from get_queryset()

### Others

- The SECRET_KEY should not start with a dollar sign (\$), django-environ has problems with it (see Proxy value in the documentation)
- Multi table inheritance extensions: <https://github.com/django-polymorphic/django-polymorphic> and <https://github.com/jazzband/django-model-utils>

## Celery Manage Python API

- python manage.py shell_plus
  from adit.celery import app
  i = app.control.inspect()
  i.scheduled()
  app.AsyncResult("task_id").state

## DICOM

### pydicom and datetime

- To automatically convert dates to the datetime.date class this config must be set explicitly (default is False): config.datetime_conversion = True
- Then the type is valuerep.DA (<https://pydicom.github.io/pydicom/dev/reference/generated/pydicom.valuerep.DA.html#>) which is an instance of datetime.date
- Otherwise dates and times are represented as strings (e.g. 19760831)
- Same is true for datetime.time (valuerep.DT)

### C-CANCEL support

- GE simply aborts the association on a C-CANCEL request, but only after some time (maybe 20 seconds or so).
- So it seems C-CANCEL is not well supported. We better abort the association just ourself and create a new association for further requests.

### Parallel C-MOVE requests to download images

- This is much more complicated than C-GET as only one C-MOVE storage SCP as destination can be chosen.
- So the images of multiple C-MOVE SCU requests go to the same destination and must be somehow routed there.
- The only option seems to use MoveOriginatorMessageID (see <https://stackoverflow.com/q/14259852/166229>), which unfortunately is option in the DICOM standard.
- Other systems have the same issue: 'Warning: the PACS station server must support the "Move Originator Message ID" (0000,1031) and "Move Originator Application Entity Title" (0000,1030) when sending CSTORE messages during processing CMOVE operations.', see <http://www.onis-viewer.com/PluginInfo.aspx?id=42>

## Docker

- To deal with the below error message while starting docker containers just execute in WSL Ubuntu: `sudo hwclock -s`

```txt
E: Release file for http://security.debian.org/debian-security/dists/buster/updates/InRelease is not valid yet (invalid for another 1h 22min 32s). Updates for this repository will not be applied.
E: Release file for http://deb.debian.org/debian/dists/buster-updates/InRelease is not valid yet (invalid for another 17h 37min 38s). Updates for this repository will not be applied.
```

## Gitpod

- It is not possible to set an ENV variable using the Gitpod Dockerfile
- In Gitpod ENV variables can only be set using the Gitpod settings
- The PYTHONPATH environment variable can't be set in the Gitpod settings (it is always overwritten with a blank value)
- What is ALLOWED_HOSTS? <https://www.divio.com/blog/django-allowed-hosts-explained/>

## Commands

### Testing and coverage commands

- docker exec -it adit_dev_web_1 pytest
- ptw --runner 'pytest -s --testmon' # Watch only changed tests with pytest watch
- python manage.py test -v 2 app_name # Show print outputs during test
- coverage run --source=. -m pytest # Run coverage only
- coverage report # Show coverage report
- coverage annotate # Annotate files with coverage
- pytest --cov=. # Run Pytest and report coverage (in one command)
- find . -name "\*,cover" -type f -delete # Delete all cover files (from coverage annotate)

### Django commands

- python manage.py shell_plus --print-sql # Show all SQL statements (django_extensions required)
- python .\manage.py startapp new_app .\adit\new_app # Folder must already exist

### Docker comands

- docker compose -f "docker-compose.dev.yml" -p adit_dev exec web pytest # Run Pytest on web container
- docker compose -f "docker-compose.dev.yml" -p adit_dev exec web pytest --cov=./adit # Run Pytest with coverage report
- docker build . --target development -t adit_dev # Build a volume from our Dockerfile
- docker run -v C:\Users\kaisc\Projects\adit:/src -it adit_dev /bin/bash # Run the built container with src folder mounted from host
- docker ps -a --filter volume=vol_name # Find container that mounts volume
- docker run -v=adit_web_data:/var/www/adit -it busybox /bin/sh # Start interactive shell with named volume mounted
- docker run --rm -i -v=adit_web_data:/foo busybox find /foo # List files in named volume
- docker compose -f "docker-compose.dev.yml" -p adit_dev up -d --build
- docker compose -f "docker-compose.prod.yml" -p adit_prod up -d --build

### Celery commands

- celery -A adit purge -Q default,low
- celery -A adit inspect scheduled

## Deployment for production

- Copy cert.pem and key.pem from N:\Dokumente\Projekte\ADIT_Server\ssl_certificate to /var/www/adit/ssl/
- Restart adit_prod_web container
- Add the DICOM servers and folders

## Python

- <https://realpython.com/documenting-python-code/>
- <https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html>
