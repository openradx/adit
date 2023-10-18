from django.contrib import admin

from .models import ReportsAppSettings

admin.site.register(ReportsAppSettings, admin.ModelAdmin)
