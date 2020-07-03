[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/medihack/adit)


# TODO
- rename row_id / RowID to ransfer_id / TransferID

# Commands

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

# Planing

transfer(node1, node2):
    no1