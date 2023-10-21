from django.contrib import admin

from .models import SearchAppSettings

admin.site.register(SearchAppSettings, admin.ModelAdmin)
