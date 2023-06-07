from django.contrib import admin

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import BatchQueryJob, BatchQuerySettings, BatchQueryTask

admin.site.register(BatchQueryJob, DicomJobAdmin)

admin.site.register(BatchQueryTask, DicomTaskAdmin)

admin.site.register(BatchQuerySettings, admin.ModelAdmin)
