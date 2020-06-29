[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/medihack/adit)

# Commands

## Watch only changed tests with pytest watch
ptw --runner 'pytest -s --testmon'

## Kill supervisord
cat /tmp/supervisord.pid | kill -s SIGTERM '{print $1}'

## Shell with show all excecuted SQL statements
python manage.py shell_plus --print-sql

# Ports in development
- 8000 Django Webserver (development)
- 5432 PostreSQL
- 9001 Supervisord Webserver
- 6379 Redis Server
- 7501 Orthanc 1 DICOM
- 7502 Orhtanc 2 DICOM
- 6501 Orthanc 1 Webserver
- 6502 Orthanc 2 Webserver

#  Used dicom images from
- https://wiki.cancerimagingarchive.net/display/Public/RIDER+PHANTOM+MRI
- https://wiki.cancerimagingarchive.net/display/Public/Collections

# Planned fields for BatchTransferJob model
max_period_size = models.PositiveIntegerField(default=100)
    enforced_break = models.PositiveIntegerField(default=2000)
    interval_start_time = models.TimeField()
    interval_end_time = models.TimeField()

# Resources

## Testing
- https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django