from django.contrib import admin

# Register your models here.
from .models import UploadSession, UploadSettings

admin.site.register(UploadSettings, admin.ModelAdmin)


class UploadStatisticAdmin(admin.ModelAdmin):
    list_display = (
        "get_owner",
        "id",
        "time_opened",
        "get_size_in_mb",
        "uploaded_file_count",
    )
    list_filter = ("time_opened", "owner")
    search_fields = ("owner__username",)

    def get_owner(self, obj):
        return obj.owner.username

    get_owner.admin_order_field = "owner__username"
    get_owner.short_description = "Owner"

    def get_size_in_mb(self, obj):
        return f"{obj.upload_size / (1024 * 1024):.2f} MB"

    get_size_in_mb.short_description = "Upload Size"


admin.site.register(UploadSession, UploadStatisticAdmin)
