from django.contrib import admin
from .models import Access


class AccessAdmin(admin.ModelAdmin):
    list_display = ("name",
                    "access_type",
                    "group",
                    "node")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Access, AccessAdmin)