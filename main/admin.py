from django.contrib import admin
from .models import DicomServer, DicomPath, TransferJob

admin.site.site_header = 'ADIT administration'

class DicomServerAdmin(admin.ModelAdmin):
    list_display = ('node_id', 'node_name')
    exclude = ('node_type',)

class DicomPathAdmin(admin.ModelAdmin):
    list_display = ('node_id', 'node_name')
    exclude = ('node_type',)

class TransferJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'job_type', 'status', 'source', 'destination')

admin.site.register(DicomServer, DicomServerAdmin)
admin.site.register(DicomPath, DicomPathAdmin)
admin.site.register(TransferJob, TransferJobAdmin)