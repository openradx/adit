from django.contrib import admin

# Register your models here.
from .models import UploadSettings

admin.site.register(UploadSettings, admin.ModelAdmin)
