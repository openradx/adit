from django.contrib import admin
from .models import SelectiveTransferSettings, SelectiveTransferJob


class SelectiveTransferJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source",
        "destination",
        "status",
        "created",
        "get_owner",
    )

    list_filter = ("status", "created", "owner")
    search_fields = ("owner__username",)

    def get_owner(self, obj):  # pylint: disable=no-self-use
        return obj.owner.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "owner__username"


admin.site.register(SelectiveTransferJob, SelectiveTransferJobAdmin)


admin.site.register(SelectiveTransferSettings, admin.ModelAdmin)
