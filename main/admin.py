from django.contrib import admin
from .models import DicomServer, DicomPath, TransferJob

class DicomServerAdmin(admin.ModelAdmin):
    pass

class DicomPathAdmin(admin.ModelAdmin):
    pass

class TransferJobAdmin(admin.ModelAdmin):
    pass

admin.site.register(DicomServer, DicomServerAdmin)
admin.site.register(DicomPath, DicomPathAdmin)
admin.site.register(TransferJob, TransferJobAdmin)