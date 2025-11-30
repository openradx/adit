from django.contrib import admin

from .models import APISession, DicomWebSettings

admin.site.register(DicomWebSettings, admin.ModelAdmin)


class APISessionAdmin(admin.ModelAdmin):
    list_display = (
        "get_owner",
        "id",
        "time_last_accessed",
        "total_number_requests",
        "get_size",
    )
    list_filter = ("total_number_requests", "owner")
    search_fields = ("owner__username",)

    def get_owner(self, obj):
        return obj.owner.username

    get_owner.admin_order_field = "owner__username"
    get_owner.short_description = "Owner"

    def get_size(self, obj):
        size = obj.total_transfer_size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024

    get_size.short_description = "Total Transfer Size"


admin.site.register(APISession, APISessionAdmin)
