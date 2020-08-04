[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/medihack/adit)


# TODO
- Add license file
- Pseudonymize BirthDate
- Think about moving all those dicts to dataclasses when passing around data
-- Allow provide a regex of StudyDescription in CSV batch file
-- Allow to specify many modalities per row in CSV file
- rename DicomJob to TransferJob

# Testing and coverage commands
ptw --runner 'pytest -s --testmon'   # Watch only changed tests with pytest watch
python manage.py test -v 2 app_name   # Show print outputs during test
coverage run --source=. -m pytest   # Run coverage only
coverage report   # Show coverage report
coverage annotate   # Annotate files with coverage
pystest --cov=.   # Run Pytest and report coverage (in one command)
find . -name "*,cover" -type f -delete   # Delete all cover files (from coverage annotate)

# Supervisor commands
supervisord   # Start supervisor daemon
supervisorctl  # Supervisor control shell
supervisorctl shutdown  # Shut down supervisor daemon

# Django shell commands
python manage.py shell_plus --print-sql  # Show all SQL statements (django_extensions required)

# Ports in development
- see .gitpod.yml file

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

# ContinousTransferJob
- Fields: job_name, from, till (optional), dicom_tag_regex