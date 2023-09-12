from django.contrib import admin

from .models import CoreSettings

admin.site.site_header = "RADIS administration"


admin.site.register(CoreSettings, admin.ModelAdmin)
