from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group

from .forms import GroupAdminForm
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


class MyGroupAdmin(GroupAdmin):
    form = GroupAdminForm


admin.site.unregister(Group)
admin.site.register(Group, MyGroupAdmin)


class InstituteAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    ordering = ("name",)
    filter_horizontal = ("users",)


admin.site.register(Institute, InstituteAdmin)
