from django.contrib import admin

from .models import Collection, CollectionsAppSettings

admin.site.register(CollectionsAppSettings, admin.ModelAdmin)

admin.site.register(Collection, admin.ModelAdmin)
