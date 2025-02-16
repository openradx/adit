from django.contrib import admin

from adit_server.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import SelectiveTransferJob, SelectiveTransferSettings, SelectiveTransferTask

admin.site.register(SelectiveTransferJob, DicomJobAdmin)

admin.site.register(SelectiveTransferTask, DicomTaskAdmin)

admin.site.register(SelectiveTransferSettings, admin.ModelAdmin)
