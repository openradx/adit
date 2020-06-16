from django.contrib import admin
from .models import DicomServer, DicomPath, TransferJob

admin.site.site_header = 'ADIT administration'

class DicomServerAdmin(admin.ModelAdmin):
    exclude = ('node_type',)

class DicomPathAdmin(admin.ModelAdmin):
    exclude = ('node_type',)

class TransferJobAdmin(admin.ModelAdmin):
    pass

admin.site.register(DicomServer, DicomServerAdmin)
admin.site.register(DicomPath, DicomPathAdmin)
admin.site.register(TransferJob, TransferJobAdmin)