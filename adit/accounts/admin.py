from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group

from adit.core.models import DicomNodeGroupAccess

from .forms import GroupAdminForm
from .models import User


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


class DicomNodeGroupAccessInline(admin.TabularInline):
    model = DicomNodeGroupAccess
    extra = 1
    ordering = ("group__name",)


class MyGroupAdmin(GroupAdmin):
    form = GroupAdminForm
    inlines = (DicomNodeGroupAccessInline,)


admin.site.unregister(Group)
admin.site.register(Group, MyGroupAdmin)
