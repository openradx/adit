from django.contrib import admin
from .models import AppSettings, BatchTransferJob


class BatchTransferJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project_name",
        "source",
        "destination",
        "status",
        "created",
        "get_owner",
    )

    list_filter = ("status", "created", "owner")
    search_fields = ("project_name", "owner__username")

    def get_owner(self, obj):  # pylint: disable=no-self-use
        return obj.owner.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "owner__username"


admin.site.register(BatchTransferJob, BatchTransferJobAdmin)


class AppSettingsAdmin(admin.ModelAdmin):
    pass


admin.site.register(AppSettings, AppSettingsAdmin)
