from django.contrib import admin
from .models import DicomServer, DicomPath

admin.site.site_header = 'ADIT administration'

class DicomServerAdmin(admin.ModelAdmin):
    list_display = ('node_name', 'ae_title', 'ip', 'port')
    exclude = ('node_type',)

admin.site.register(DicomServer, DicomServerAdmin)

class DicomPathAdmin(admin.ModelAdmin):
    list_display = ('node_name', 'path')
    exclude = ('node_type',)

admin.site.register(DicomPath, DicomPathAdmin)
