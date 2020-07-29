[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/medihack/adit)


# TODO
- Add license file
- Pseudonymize BirthDate
- Think about moving all those dicts to dataclasses when passing around data
-- Allow provide a regex of StudyDescription in CSV batch file
-- Allow to specify many modalities per row in CSV file

# Commands

## Test with manage.py
- Show print outputs: python manage.py -v 2 app_name

## Watch only changed tests with pytest watch
ptw --runner 'pytest -s --testmon'

## supervisord
- Start supervisord: `supervisord`
- Show all control commands: `supervisorctl help`
- Shutdown supervisord: `supervisorctl shutdown`

## Django shells
- Show all SQL statements (needs django_extensions): `python manage.py shell_plus --print-sql`

# Ports in development
- see .gitpod.yml file

#  Used dicom images from
- https://wiki.cancerimagingarchive.net/display/Public/RIDER+PHANTOM+MRI
- https://wiki.cancerimagingarchive.net/display/Public/Collections


# Planned fields for BatchTransferJob model
max_period_size = models.PositiveIntegerField(default=100)
    enforced_break = models.PositiveIntegerField(default=2000)
    interval_start_time = models.TimeField()
    interval_end_time = models.TimeField()

# Resources

## supervisord
- https://medium.com/@jayden.chua/use-supervisor-to-run-your-python-tests-13e91171d6d3

## Testing
- https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django

# Knowledge
- It is not possible to set an ENV variable using the Gitpod Dockerfile
- In Gitpod ENV variables can only be set using the Gitpod settings
- The PYTHONPATH environment variable can't be set in the Gitpod settings (it is always overwritten with a blank value)
- What is ALLOWED_HOSTS? https://www.divio.com/blog/django-allowed-hosts-explained/
- The SECRET_KEY should not start with a dollar sign ($), django-environ has problems with it (see Proxy value in the documentation)