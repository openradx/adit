from django.contrib import admin

from .models import (
    CoreSettings,
    DicomFolder,
    DicomJob,
    DicomNodeGroupAccess,
    DicomServer,
    DicomTask,
    QueuedTask,
)

admin.site.site_header = "ADIT administration"

admin.site.register(CoreSettings, admin.ModelAdmin)


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


class QueuedTaskAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "content_object",
        "priority",
        "created",
        "locked",
        "eta",
    )


admin.site.register(QueuedTask, QueuedTaskAdmin)


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


class DicomNodeGroupAccessInline(admin.TabularInline):
    model = DicomNodeGroupAccess
    extra = 1
    ordering = ("group__name",)


class DicomServerAdmin(admin.ModelAdmin):
    list_display = ("name", "ae_title", "host", "port")
    exclude = ("node_type",)
    inlines = (DicomNodeGroupAccessInline,)


admin.site.register(DicomServer, DicomServerAdmin)


class DicomFolderAdmin(admin.ModelAdmin):
    list_display = ("name", "path")
    exclude = ("node_type",)
    inlines = (DicomNodeGroupAccessInline,)


admin.site.register(DicomFolder, DicomFolderAdmin)
