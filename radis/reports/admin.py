from django.contrib import admin

from .models import ReportsSettings

admin.site.register(ReportsSettings, admin.ModelAdmin)
