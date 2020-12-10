# Django

## FilterMixin does not work in DetailView

-   DetailView queries the object in get_object() using the get_queryset()
-   This collides with FilterMixin as it also gets its data from get_queryset()

## Others

-   The SECRET_KEY should not start with a dollar sign (\$), django-environ has problems with it (see Proxy value in the documentation)
-   Multi table inheritance extensions: https://github.com/django-polymorphic/django-polymorphic and https://github.com/jazzband/django-model-utils

# Celery Manage Python API

-   python manage.py shell_plus
    from adit.celery import app
    i = app.control.inspect()
    i.scheduled()
    app.AsyncResult("task_id").state

# DICOM

## pydicom and datetime

-   To automatically convert dates to the datetime.date class this config must be set explicitly (default is False): config.datetime_conversion = True
-   Then the type is valuerep.DA (https://pydicom.github.io/pydicom/dev/reference/generated/pydicom.valuerep.DA.html#) which is an instance of datetime.date
-   Otherwise dates and times are represented as strings (e.g. 19760831)
-   Same is true for datetime.time (valuerep.DT)

## C-CANCEL support

-   GE simply aborts the association on a C-CANCEL request, but only after some time (maybe 20 seconds or so).
-   So it seems C-CANCEL is not well supported. We better abort the association just ourself and create a new association for further requests.

## Parallel C-MOVE requests to download images

-   This is much more complicated than C-GET as only one C-MOVE storage SCP as destination can be chosen.
-   So the images of multiple C-MOVE SCU requests go to the same destination and must be somehow routed there.
-   The only option seems to use MoveOriginatorMessageID (see https://stackoverflow.com/q/14259852/166229), which unfortunately is option in the DICOM standard.
-   Other systems have the same issue: 'Warning: the PACS station server must support the "Move Originator Message ID" (0000,1031) and "Move Originator Application Entity Title" (0000,1030) when sending CSTORE messages during processing CMOVE operations.', see http://www.onis-viewer.com/PluginInfo.aspx?id=42

# Gitpod

-   It is not possible to set an ENV variable using the Gitpod Dockerfile
-   In Gitpod ENV variables can only be set using the Gitpod settings
-   The PYTHONPATH environment variable can't be set in the Gitpod settings (it is always overwritten with a blank value)
-   What is ALLOWED_HOSTS? https://www.divio.com/blog/django-allowed-hosts-explained/
