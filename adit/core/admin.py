from django.contrib import admin

from .models import (
    CoreSettings,
    DicomFolder,
    DicomJob,
    DicomNodeInstituteAccess,
    DicomServer,
    DicomTask,
)

admin.site.site_header = "ADIT administration"


class DicomJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "created",
        "get_owner",
    )

    list_filter = ("status", "created", "owner")
    search_fields = ("owner__username",)

    def get_owner(self, obj: DicomJob):
        return obj.owner.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "owner__username"


class DicomTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "created",
        "start",
        "end",
        "get_owner",
    )

    list_filter = ("status", "created")
    search_fields = ("job__id",)

    def get_owner(self, obj: DicomTask):
        return obj.job.owner.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "job__owner__username"


class DicomNodeInstituteAccessInline(admin.TabularInline):
    model = DicomNodeInstituteAccess
    extra = 1
    ordering = ("institute__name",)


class DicomServerAdmin(admin.ModelAdmin):
    list_display = ("name", "ae_title", "host", "port")
    exclude = ("node_type",)
    inlines = (DicomNodeInstituteAccessInline,)


admin.site.register(DicomServer, DicomServerAdmin)


class DicomFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "path")
    exclude = ("node_type",)
    inlines = (DicomNodeInstituteAccessInline,)


admin.site.register(DicomFolder, DicomFolderAdmin)


admin.site.register(CoreSettings, admin.ModelAdmin)
