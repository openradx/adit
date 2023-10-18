from django.contrib import admin

from .models import CollectedReport, Collection, CollectionsAppSettings

admin.site.register(CollectionsAppSettings, admin.ModelAdmin)

admin.site.register(Collection, admin.ModelAdmin)

admin.site.register(CollectedReport, admin.ModelAdmin)
