from django.contrib import admin

from .models import CoreSettings

admin.site.site_header = "ADIT administration"


admin.site.register(CoreSettings, admin.ModelAdmin)
