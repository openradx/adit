from django.contrib import admin

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import BatchTransferJob, BatchTransferSettings, BatchTransferTask

admin.site.register(BatchTransferJob, DicomJobAdmin)

admin.site.register(BatchTransferTask, DicomTaskAdmin)

admin.site.register(BatchTransferSettings, admin.ModelAdmin)
