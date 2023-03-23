from django.contrib import admin
from .models import DicomQidoJob, DicomQidoSettings


class DicomQidoJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "source",
        "get_owner",
    )

    list_filter = ("status", "owner", "source")
    search_fields = ("owner", "source")

    def get_owner(self, obj):
        return obj.owner.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "owner__username"


admin.site.register(DicomQidoJob, DicomQidoJobAdmin)

admin.site.register(DicomQidoSettings, admin.ModelAdmin)
