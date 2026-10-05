from typing import Any, cast

from adit_radis_shared.accounts.models import User
from django.contrib import admin
from django.http import HttpRequest

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .forms import RoutingRuleForm
from .models import RouterBatch, RouterJob, RouterSender, RouterSettings, RouterTask, RoutingRule


class RouterSenderAdmin(admin.ModelAdmin):
    list_display = ("calling_ae_title", "server", "enabled")
    list_filter = ("enabled",)


class RoutingRuleAdmin(admin.ModelAdmin):
    form = RoutingRuleForm
    list_display = ("name", "enabled", "destination", "pseudonymize", "created_by")
    list_filter = ("enabled",)

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> list[str]:
        fields = ["created_by", "created", "updated"]
        if obj is not None and obj.jobs.exists():
            # A patient must keep the same pseudonym under a rule.
            fields += ["pseudonymize", "pseudonym_salt"]
        return fields

    def get_form(
        self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any
    ) -> Any:
        form_class = cast(type[RoutingRuleForm], super().get_form(request, obj, change, **kwargs))
        user = cast(User, request.user)

        # The admin creates the form itself, so the subclass hands over the user.
        class UserRoutingRuleForm(form_class):
            def __init__(self, *args: Any, **form_kwargs: Any) -> None:
                super().__init__(*args, user=user, **form_kwargs)

        return UserRoutingRuleForm

    def save_model(self, request: HttpRequest, obj: Any, form: Any, change: bool) -> None:
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class RouterBatchAdmin(ReadOnlyAdmin):
    list_display = (
        "batch_id",
        "sender",
        "study_instance_uid",
        "number_of_images",
        "closed_at",
        "files_deleted_at",
    )


class RouterJobAdmin(ReadOnlyAdmin, DicomJobAdmin):
    list_display = (*DicomJobAdmin.list_display, "rule", "batch")


class RouterTaskAdmin(ReadOnlyAdmin, DicomTaskAdmin):
    pass


admin.site.register(RouterSender, RouterSenderAdmin)
admin.site.register(RouterSettings, admin.ModelAdmin)
admin.site.register(RoutingRule, RoutingRuleAdmin)
admin.site.register(RouterBatch, RouterBatchAdmin)
admin.site.register(RouterJob, RouterJobAdmin)
admin.site.register(RouterTask, RouterTaskAdmin)
