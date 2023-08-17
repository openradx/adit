# TODO

## Top

- Type hints of template tags
- Fix some stuff and use our fork then of DICOMwebClient
  -- <https://github.com/ImagingDataCommons/dicomweb-client/issues/88>
  -- <https://github.com/ImagingDataCommons/dicomweb-client/issues/89>
- Look into how we can improve STOW (do we have to upload one file at a time, can we stream it somehow)
  -- test_stowrs takes forever as many files get uploaded ... reduce this
- Look into how we can stream the file with WADO
- Remove files in test folders from autoreload
- Rewrite dicom connector without converting DataSet to dict
  -- Make Unit test using pynetdicom test dummy servers
- Check why Alpine script must used as type="module"
- Make job urgent (as staff member)
- Selective transfer choose series
- Locked info for other apps like batch_transfer_locked.html
- Hint when app is locked for admin user
- Split messages into toasts (client only) and messages from server (using Bootstrap alerts)
- Rewrite Celery unit tests using the official test helpers
- Check why this dicomweb test takes so long
- Use pynetdicom SCPs instead of Orthancs in integrations tests
  -- Find those tests by looking for "setup_orthancs" fixture

## High Priority

- Redirect after restart/retry/delete job
- Option if you want an Email when job ends (make it optional)
- Option in batch query to query whole study or explicit series
- Allow to terminate a specific Celery task with revoke(task_id, terminate=True)
- Make whole receiver crash if one asyncio task crashes
- Auto refresh job pages und success or failure
- Rewrite tests to use mocker fixture instead of patch
- rename ADIT_AE_TITLE to RECEIVER_AE_TITLE
- Query with StudyDateStart, StudyDateEnd, StudyDate
- Common search query Websocket component
- DICOM Explorer localstorage source
- Refactor \_message_panel.html
- QueryUtil -> QueryExecutor, and TransferUtil -> TransferExecutor
- Improve cancel during transfer
- Allow admin to kill a job (with task revoke(terminate=True))
- Fix the ineffective stuff in transfer_utils, see TODO there
- Write test_parsers.py
- DICOM data that does not need to be modified can be directly transferred between the source and destination server (C-MOVE). The only exception is when source and destination server are the same, then the data will still be downloaded and uploaded again. This may be helpful when the PACS server treats the data somehow differently when sent by ADIT.
- Move source and target from DICOM job to DICOM task
  -- That way we can transfer from multiple sources to a destination in one job
- Check if we still need Abortable Celery Tasks (and just use Task)
  -- Currently we don't use this functionality to abort running task, but we could
  -- <https://docs.celeryq.dev/en/stable/reference/celery.contrib.abortable.html>
  -- <https://docs.celeryq.dev/en/latest/faq.html#how-do-i-get-the-result-of-a-task-if-i-have-the-id-that-points-there>
- Use Django ORM as Celery result backend (currently we use Redis for that)
  -- <https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html#django-celery-results-using-the-django-orm-cache-as-a-result-backend>

## Fix

- Do some prechecks before trying the task (is source and destination online?)
- Fix Celery logging (task ids are not appended to logging messages even as we use get_task_logger)
- Shorter timeout for offline studies
- Tests: test_query_utils, test serializers, test all views (as integration tests using real Orthanc), improve tests of transferutil, BatchFileSizeError
- c-get download timeout
- Choice to transfer all modalities of a studies or just the modalities which were searched for
- Make logging analyze Docker image with: <http://crunchtools.com/software/petit/>, less, vim, <https://crypt.gen.nz/logsurfer/>, ripgrep
- Evaluate (0008, 0056) Instance Availability CS: 'OFFLINE' ( (ONLINE, NEARLINE, OFFLINE, UNAVAILABLE)), see <https://www.gehealthcare.com/-/jssmedia/1b62d771fb604ff7a4c8012498aea68b.pdf?la=en-us>

## Features

- New batch transfer
  -- Create new batch transfer job and allow to add tasks
  -- Add tasks manually or using a Excel file
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

- Upgrade postgres server to v15, but we have to migrate the data then as the database files are incompatible a newer version
  -- <https://hollo.me/devops/upgrade-postgresql-database-with-docker.html>
  -- <https://thomasbandt.com/postgres-docker-major-version-upgrade>
  -- <https://betterprogramming.pub/how-to-upgrade-your-postgresql-version-using-docker-d1e81dbbbdf9>
  -- look into <https://github.com/tianon/docker-postgres-upgrade>
- Get rid of 7z archive feature. It think it was never used.
- Allow to search multiple source servers with one query (maybe only in dicom explorer)
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
- Evaluate if services should be better restarted with pywatchman instead of watchdog and watchmedo
  -- pywatchman is used by Django autoreload
  -- See <https://github.com/django/django/blob/main/django/utils/autoreload.py>
  -- Unfortunately, I could not get it to work with Django autoreload itself, but we can use something similiar by using watchman directly and integrate it in ServerCommand
- BatchQuery with custom DICOM keywords
- Watchdog server
- pull celery_task stuff out of transfer_utils
- Allow provide a regex of StudyDescription in batch file
- move date parsing part in parsers.py and consumers.py to date_util.py
- <https://stackoverflow.com/questions/14259852/how-to-identify-image-receive-in-c-store-as-result-of-a-c-move-query>
- <https://www.yergler.net/2009/09/27/nested-formsets-with-django/>
- <http://the-frey.github.io/2014/08/18/monitoring-docker-containers-with-monit>
- move or get rid of hijack_logger and store_log_in_task in task_utils
- Use LRU cache for dicom explorer / collector (don't we already do this?!)
- log debug -> info in connector also in production
- Link owner in templates to user profile
- Rewrite dicom_connector to use asyncio (wrap all pynetdicom calls in asyncio.to_thread)
  -- I don't think that this will gain any performance improvements, so maybe not worth it
- Look out for a django-revproxy fix (see <https://github.com/jazzband/django-revproxy/issues/144>)
  -- Flower and Rabbit Management Console are running behind a Django internal reverse proxy (django-revproxy) so that only admins can access them
  -- Unfortunately the last released django-revproxy is broken with latest Django
  -- So we use the master branch here directly from Github (see pyproject.toml)
  -- Alternatively we could use <https://github.com/thomasw/djproxy>
- Rethink task queues and rescheduling
  -- Currently we use Celery to schedule tasks in the future using Celery's ETA feature, but this is not recommended for tasks in the distant future (see <https://docs.celeryq.dev/en/stable/userguide/calling.html#eta-and-countdown>)
  -- An option would be to introduce a "rescheduled" property in task model and reschedule them by checking periodically using Celery Beat PeriodicTasks (maybe every hour or so) or using "one_off" PeriodicTasks.
  -- But then we can't use Celery Canvas anymore as tasks in a worker finish with such a rescheduling outside of the Celery queue system. We then have to check at the end of each task if the job is finished or erroneous (by checking all the other sibling tasks). This should be done with a distributed lock (e.g. using <https://sher-lock.readthedocs.io/en/latest/>) so that if we have multiple workers there are no race conditions.
  -- Maybe it isn't even a big problem as in a hospital site we never accumulate such many Celery tasks on a worker and ETA is totally fine (just keep it in mind that it could get a problem).
  -- Make sure if using PeriodicTask that those are also cancelled when job is cancelled.
  -- Another solution would be to use Temporal.io as soon as they implement task priorities <https://github.com/temporalio/temporal/issues/1507>
- Evaluate other task runners
  -- <https://www.pyinvoke.org/> # used currently
  -- <https://github.com/taskipy/taskipy>
  -- <https://github.com/nat-n/poethepoet>
  -- <https://just.systems/>
- Make a job urgent retrospectively (maybe only staff members can do this)
  -- A current workaround is to cancel the job, change urgency with Django Admin and then resume the job
- Try to bring channels_liver_server in official pytest_django release
  -- <https://github.com/pytest-dev/pytest-django/blob/master/pytest_django/fixtures.py#L514>
  -- <https://github.com/pytest-dev/pytest-django/blob/42b7db2f4f5dbe785e57652d1d4ea9eda39e56e3/pytest_django/live_server_helper.py#L4>
  -- <https://github.com/django/channels/blob/main/channels/testing/live.py#L21>
  -- <https://github.com/django/daphne/blob/main/daphne/testing.py#L123>
  -- <https://github.com/django/django/blob/main/django/test/testcases.py#L1810>
- Maybe move label from from form to models using "verbose_name" and also the help_text
- Save specific form fields for later use with HTMX, currently we only save them in the post handler when the form is valid.
- Move user profile fields from User to a related UserProfile model. Improves the query performance a bit, but not sure if it is worth it.
- Setup pgadmin
  -- <https://stackoverflow.com/questions/64620446/adding-postgress-connections-to-pgadmin-in-docker-file>
  -- Not sure if we really need this as we have Django admin and can view data in there
- Move to SVG sprite (the stuff with symbol) instead of including the SVGs itself
  -- See <https://getbootstrap.com/docs/5.0/components/alerts/#icons>

## RADIS

- Get rid of jQuery in ADIT and RADIS
- Get rid of Jumbotron
- Get rid of those not used accounts views and login form
