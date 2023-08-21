from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from adit.core.models import DicomNodeInstituteAccess

from .models import Institute, User


class MyUserAdmin(UserAdmin):
    ordering = ("date_joined",)
    list_display = (
        "username",
        "email",
        "date_joined",
        "first_name",
        "last_name",
        "is_staff",
    )
    change_form_template = "loginas/change_form.html"


admin.site.register(User, MyUserAdmin)


class DicomNodeInstituteAccessInline(admin.TabularInline):
    model = DicomNodeInstituteAccess
    extra = 1
    ordering = ("institute__name",)


class InstituteAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    ordering = ("name",)
    filter_horizontal = ("users",)
    inlines = (DicomNodeInstituteAccessInline,)


admin.site.register(Institute, InstituteAdmin)
