from django.contrib import admin

from .models import DicomWebSettings

admin.site.register(DicomWebSettings, admin.ModelAdmin)
