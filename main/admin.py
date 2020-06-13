from django.contrib import admin
from .models import DicomServer, DicomPath

class DicomServerAdmin(admin.ModelAdmin):
    pass

class DicomPathAdmin(admin.ModelAdmin):
    pass

admin.site.register(DicomServer, DicomServerAdmin)
admin.site.register(DicomPath, DicomPathAdmin)