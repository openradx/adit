from django.contrib import admin

from .models import BatchQueryJob, BatchQuerySettings


class BatchQueryJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project_name",
        "source",
        "status",
        "created",
        "get_owner",
    )

    list_filter = ("status", "created", "owner")
    search_fields = ("project_name", "owner__username")

    def get_owner(self, obj):
        return obj.owner.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "owner__username"


admin.site.register(BatchQueryJob, BatchQueryJobAdmin)

admin.site.register(BatchQuerySettings, admin.ModelAdmin)
