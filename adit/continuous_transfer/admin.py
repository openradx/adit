from django.contrib import admin

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import ContinuousTransferJob, ContinuousTransferSettings, ContinuousTransferTask

admin.site.register(ContinuousTransferJob, DicomJobAdmin)

admin.site.register(ContinuousTransferTask, DicomTaskAdmin)

admin.site.register(ContinuousTransferSettings, admin.ModelAdmin)
