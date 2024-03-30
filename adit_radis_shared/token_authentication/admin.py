from django.contrib import admin

from .models import Token


class TokenAdmin(admin.ModelAdmin):
    list_display = (
        "fraction",
        "description",
        "owner",
        "created_time",
        "expires",
        "last_used",
    )

    list_filter = ("owner", "created_time", "last_used", "expires")
    search_fields = ("owner",)


admin.site.register(Token, TokenAdmin)
