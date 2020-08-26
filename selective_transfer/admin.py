from django.contrib import admin
from .models import AppSettings, SelectiveTransferJob


class SelectiveTransferJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "destination",
        "status",
        "created_at",
        "get_creator",
    )

    list_filter = ("status", "created_at", "created_by")
    search_fields = ("created_by__username",)

    def get_creator(self, obj):  # pylint: disable=no-self-use
        return obj.created_by.username

    get_creator.short_description = "Creator"
    get_creator.admin_order_field = "created_by__username"


admin.site.register(SelectiveTransferJob, SelectiveTransferJobAdmin)


class AppSettingsAdmin(admin.ModelAdmin):
    pass


admin.site.register(AppSettings, AppSettingsAdmin)
