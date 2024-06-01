from django.contrib import admin

# Register your models here.
from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import UploadJob, UploadSettings, UploadTask

admin.site.register(UploadJob, DicomJobAdmin)
admin.site.register(UploadTask, DicomTaskAdmin)
admin.site.register(UploadSettings, admin.ModelAdmin)
