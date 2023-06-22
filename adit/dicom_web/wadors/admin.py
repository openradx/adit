from django.contrib import admin

from .models import DicomWadoJob, DicomWadoSettings


class DicomWadoJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "source",
        "get_owner",
    )

    list_filter = ("status", "owner", "source")
    search_fields = ("owner", "source")

    def get_owner(self, obj):  # pylint: disable=no-self-use
        return obj.owner.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "owner__username"


admin.site.register(DicomWadoJob, DicomWadoJobAdmin)

admin.site.register(DicomWadoSettings, admin.ModelAdmin)
