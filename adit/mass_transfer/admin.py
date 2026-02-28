from django.contrib import admin

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import (
    MassTransferAssociation,
    MassTransferFilter,
    MassTransferJob,
    MassTransferSettings,
    MassTransferTask,
    MassTransferVolume,
)


class MassTransferJobAdmin(DicomJobAdmin):
    exclude = ("urgent",)


admin.site.register(MassTransferJob, MassTransferJobAdmin)
admin.site.register(MassTransferTask, DicomTaskAdmin)
admin.site.register(MassTransferSettings, admin.ModelAdmin)
admin.site.register(MassTransferFilter, admin.ModelAdmin)
admin.site.register(MassTransferVolume, admin.ModelAdmin)
admin.site.register(MassTransferAssociation, admin.ModelAdmin)
