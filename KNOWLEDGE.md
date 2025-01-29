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

## DICOM

- All available DICOM tags: <https://dicom.nema.org/medical/dicom/current/output/chtml/part06/chapter_6.html>

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

### Docker and proxies

Docker Compose does automatically set http_proxy, HTTP_PROXY, https_proxy,
HTTPS_PROXY, no_proxy and NO_PROXY with the values specified in
~/.docker/config.json. Unfortunately Docker Swarm does not set those value,
but those can be set by using environment variables, e.g. using an env file.
The proxy variables by the env file do overwrite the settings of config.json.
To make the proxy only available during building an image, but not when the
container runs (in Compose as in Swarm this is never the case), then set proxy
in config.json, but explicitly reset them in the env file. This seems to be
necessary as Playwright doesn't respect the no_proxy setup and may lead to
strange errors during acceptance testing.
See also <https://docs.docker.com/network/proxy/#configure-the-docker-client>
and <https://forums.docker.com/t/docker-swarm-mode-not-picking-up-proxy-configuration/132233/8?u=medihack>

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

### Docker commands

- docker build . --target development -t adit_dev # Build a volume from our Dockerfile
- docker run -v C:\Users\kaisc\Projects\adit:/src -it adit_dev /bin/bash # Run the built container with src folder mounted from host
- docker ps -a --filter volume=vol_name # Find container that mounts volume
- docker run -v=adit_dev_web_data:/var/www/web -it busybox /bin/sh # Start interactive shell with named volume mounted
- docker run --rm -i -v=adit_dev_web_data:/foo busybox find /foo # List files in named volume
- docker volume ls -f "name=adit_dev-\*" # Show all volumes that begin with "adit_dev-"
- docker volume rm $(docker volume ls -f "name=foobar-\*" -q) # Delete all volumes that begin with "foobar-", cave delete the \

### Docker compose comands

- docker compose -f "docker-compose.dev.yml" -p adit_dev exec web pytest # Run Pytest on web container
- docker compose -f "docker-compose.dev.yml" -p adit_dev exec web pytest --cov=./adit # Run Pytest with coverage report
- docker compose -f "docker-compose.dev.yml" -p adit_dev up -d --build
- docker compose -f "docker-compose.prod.yml" -p adit_prod up -d --build

### Docker swarm commands

- docker swarm init
- docker swarm join --token SWMTKN-1-3x8erolqchsrbia8u0kkrgbd8ny9e9kdv1nl83q9xxipee5buw-9f5ax65llltbx3eiq3nsbaouw 161.42.235.115:2377
- docker node ls
- docker stack deploy -c compose/docker-compose.base.yml -c compose/docker-compose.dev.yml foobar
- docker stack ls
- docker stack ps foobar
- docker stack services foobar
- docker stack rm foobar

## Deployment for production

- Copy cert.pem and key.pem from N:\Dokumente\Projekte\ADIT_Server\ssl_certificate to /var/www/web/ssl/
- Restart adit_prod_web container
- Add the DICOM servers and folders

## Python

- <https://realpython.com/documenting-python-code/>
- <https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html>
