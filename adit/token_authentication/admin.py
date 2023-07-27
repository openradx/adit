from django.contrib import admin

from .models import Token, TokenSettings


class TokenAdmin(admin.ModelAdmin):
    list_display = (
        "token_hashed",
        "owner",
        "created_time",
        "client",
        "expires",
        "last_used",
        "get_owner",
    )

    list_filter = ("owner", "created_time", "last_used", "expires")
    search_fields = ("owner",)

    def get_owner(self, obj):  # pylint: disable=no-self-use
        return obj.owner.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "owner__username"


admin.site.register(Token, TokenAdmin)
admin.site.register(TokenSettings, admin.ModelAdmin)
