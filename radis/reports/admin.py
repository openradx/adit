from django.contrib import admin

from .models import Report, ReportsAppSettings

admin.site.register(ReportsAppSettings, admin.ModelAdmin)

admin.site.register(Report, admin.ModelAdmin)
