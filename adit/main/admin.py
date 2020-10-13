from django.contrib import admin
from .models import MainSettings, DicomServer, DicomFolder

admin.site.site_header = "ADIT administration"


class DicomServerAdmin(admin.ModelAdmin):
    list_display = ("name", "ae_title", "host", "port", "active")
    exclude = ("node_type",)


admin.site.register(DicomServer, DicomServerAdmin)


class DicomFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "path", "active")
    exclude = ("node_type",)


admin.site.register(DicomFolder, DicomFolderAdmin)


admin.site.register(MainSettings, admin.ModelAdmin)
