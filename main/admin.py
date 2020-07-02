from django.contrib import admin
from .models import SiteConfig, DicomServer, DicomFolder

admin.site.site_header = 'ADIT administration'

class DicomServerAdmin(admin.ModelAdmin):
    list_display = ('node_name', 'ae_title', 'ip', 'port')
    exclude = ('node_type',)

admin.site.register(DicomServer, DicomServerAdmin)

class DicomFolderAdmin(admin.ModelAdmin):
    list_display = ('node_name', 'path')
    exclude = ('node_type',)

admin.site.register(DicomFolder, DicomFolderAdmin)

class SiteConfigAdmin(admin.ModelAdmin):
    pass

admin.site.register(SiteConfig)
