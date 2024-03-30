from django.contrib import admin

from .models import SiteProfile

admin.site.register(SiteProfile, admin.ModelAdmin)
