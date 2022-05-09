from django.contrib import admin
from .models import RestAuthToken, RestAuthSettings, RestAuthTokenManager

# Register your models here.
class RestAuthTokenAdmin(admin.ModelAdmin):
    list_display = (
        "token_string",
        "author",
        "created_time",
        "client",
        "expiry_time",
        "expires",
        "last_used",
        "get_owner",
    )

    list_filter = ("author", "created_time", "expires", "last_used", "expiry_time")
    search_fields = ("author",)

    def get_owner(self, obj):  # pylint: disable=no-self-use
        return obj.author.username

    get_owner.short_description = "Owner"
    get_owner.admin_order_field = "owner__username"


admin.site.register(RestAuthToken, RestAuthTokenAdmin)
admin.site.register(RestAuthSettings, admin.ModelAdmin)
