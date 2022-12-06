from django.contrib import admin
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import Group
from .models import User
from .forms import GroupForm


class MyGroupAdmin(GroupAdmin):
    form = GroupForm
    list_display = ["name", "pk"]

    def save_model(self, request, obj, form, change):
        # save first to obtain id
        super(GroupAdmin, self).save_model(request, obj, form, change)
        obj.user_set.clear()
        for user in form.cleaned_data['users']:
            obj.user_set.add(user)
        
        obj.GroupAccess.clear()
        for access in form.cleaned_data["accesses"]:
            obj.GroupAccess.add(access)

    def get_form(self, request, obj=None, **kwargs):
        if obj:
            self.form.base_fields['users'].initial = [o.pk for o in obj.user_set.all()]
        else:
            self.form.base_fields['users'].initial = []

        if obj:
            self.form.base_fields['accesses'].initial = [o.pk for o in obj.GroupAccess.all()]
        else:
            self.form.base_fields['accesses'].initial = []
        return GroupForm


# unregister and register again
admin.site.unregister(Group)
admin.site.register(Group, MyGroupAdmin)


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
