# TODO

## High Priority

- Use more workers
- Query with StudyDateStart, StudyDateEnd, StudyDate
- Common search query Websocket component
- DICOM Explorer localstorage source
- Refactor \_message_panel.html
- Move stuff from parser to serializer
- Test batch views
- Convert of what's possible from Alpine.js to HTMX
- Upgrade poetry
- QueryUtil -> QueryExecutor
- Improve cancel during transfer
- Allow admin to kill a job (with task revoke(terminale=True))
- Fix the ineffective stuff in transfer_utils, see TODO there
- Write test_parsers.py
- DICOM data that does not need to be modified can be directly transferred between the source and destination server. The only exception is when source and destination server are the same, then the data will still be downloaded and uploaded again. This may be helpful when the PACS server treats the data somehow differently when sent by ADIT.

## Fix

- Auto refresh batch transfer job page if not finished automagically
- Do some prechecks before trying the task (is source and destination online?)
- Shorter timeout for offline studies
- Auto refresh pages of in progress jobs
- Tests: test_query_utils, test serializers, test all views (as integration tests using real Orthanc), improve tests of transferutil, BatchFileSizeError
- c-get download timeout
- Choice to transfer all modalities of a studies or just the modalities which were searched for
- Make logging analyze Docker image with: <http://crunchtools.com/software/petit/>, less, vim, <https://crypt.gen.nz/logsurfer/>, ripgrep
- Evaluate (0008, 0056) Instance Availability CS: 'OFFLINE' ( (ONLINE, NEARLINE, OFFLINE, UNAVAILABLE)), see <https://www.gehealthcare.com/-/jssmedia/1b62d771fb604ff7a4c8012498aea68b.pdf?la=en-us>
- Use ruff for linting when VS Code extension is ready
  -- <https://github.com/charliermarsh/ruff>

## Features

- New batch transfer
  -- Create new batch transfer job and allow to add tasks
  -- Add tasks manually or using a CSV file
  -- Query tasks directly using new dicom_query_queue
  -- New status: QUERYING, READY
  -- Button: Start Transfer (only when no task is querying)
  -- Allow to add tasks to an already existing job (even if already transferred)
  -- Delete batch query
- REST API interface
  -- Maybe implement a DICOMweb interface (see <https://book.orthanc-server.com/plugins/dicomweb.html>)
- Upload portal with drag&drop
  -- Store those files perhaps in ORTHANC
  -- Preview uploaded images
  -- Allow to transfer thow uploaded image to a PACS
- Better scheduler (with day in week and times)
- Continuous transfer mode

## Maybe

- Write channels_liver_server fixture
  -- <https://github.com/pytest-dev/pytest-django/blob/master/pytest_django/fixtures.py#L514>
  -- <https://github.com/pytest-dev/pytest-django/blob/42b7db2f4f5dbe785e57652d1d4ea9eda39e56e3/pytest_django/live_server_helper.py#L4>
  -- <https://github.com/django/channels/blob/main/channels/testing/live.py#L21>
  -- <https://github.com/django/daphne/blob/main/daphne/testing.py#L123>
  -- <https://github.com/django/django/blob/main/django/test/testcases.py#L1810>
- Support Excel batch files additionally to CSV files (best by using Pandas with openpyxl)
- Bring everything behind Nginx as reverse proxy
  -- Orthanc, Flower, Rabbit Management Console should then be directly behind Nginx (without Django-revproxy)
  -- Use authentication module of nginx
  -- <http://nginx.org/en/docs/http/ngx_http_auth_request_module.html>
  -- <https://stackoverflow.com/a/70961666/166229>
  -- Evaluate Nginx vs Traefik
- Reuse authentication in integration tests
  -- <https://playwright.dev/python/docs/auth>
  -- Unfortunately, we can't use live_server fixture inside session fixtures
  -- example <https://github.com/automationneemo/PlaywrightDemoYt>
- Get rid of dicom_connector.download_study/move_study. Do everything at the series level. That way filtering series (e.g. exlcude modalities) is much easier.
- BatchQuery with custom DICOM keywords
- Watchdog server
- pull celery_task stuff out of transfer_utils
- Allow provide a regex of StudyDescription in CSV batch file
- Allow to specify many modalities per row in CSV file
- move date parsing part in parsers.py and consumers.py to date_util.py
- <https://stackoverflow.com/questions/14259852/how-to-identify-image-receive-in-c-store-as-result-of-a-c-move-query>
- <https://www.yergler.net/2009/09/27/nested-formsets-with-django/>
- Allow to search multiple source servers with one query
- Evaluate to use diffhtml instead of morphdom, see <https://diffhtml.org/api.html#inner-html>
- <http://the-frey.github.io/2014/08/18/monitoring-docker-containers-with-monit>
- split urgent to urgent and prioritize
- move or get rid of hijack_logger and store_log_in_task in task_utils
- Use LRU cache for dicom explorer / collector (don't we already do this?!)
- log debug -> info in connector also in production
- Link owner in templates to user profile
- Look out for a django-revproxy fix (see <https://github.com/jazzband/django-revproxy/issues/144>)
  -- Flower and Rabbit Management Console are running behind a Django internal reverse proxy (django-revproxy) so that only admins can access them
  -- Unfortunately the last released django-revproxy is broken with latest Django
  -- So we use the master branch here directly from Github (see pyproject.toml)
  -- Alternatively we could use <https://github.com/thomasw/djproxy>
