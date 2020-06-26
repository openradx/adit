[![Gitpod ready-to-code](https://img.shields.io/badge/Gitpod-ready--to--code-blue?logo=gitpod)](https://gitpod.io/#https://github.com/medihack/adit)

# adit

# Important manage commands
- ./manage.py shell_plus --print-sql

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