from django.contrib import admin

from .models import RouterSender, RouterSettings


class RouterSenderAdmin(admin.ModelAdmin):
    list_display = ("calling_ae_title", "server", "enabled")
    list_filter = ("enabled",)


admin.site.register(RouterSender, RouterSenderAdmin)
admin.site.register(RouterSettings, admin.ModelAdmin)
