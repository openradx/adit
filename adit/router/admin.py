from typing import Any, cast

from django import forms
from django.contrib import admin
from django.http import HttpRequest

from adit.core.admin import DicomJobAdmin, DicomTaskAdmin

from .models import RouterBatch, RouterJob, RouterSender, RouterSettings, RouterTask, RoutingRule


class RouterSenderAdmin(admin.ModelAdmin):
    list_display = ("calling_ae_title", "server", "enabled")
    list_filter = ("enabled",)


class RoutingRuleAdminForm(forms.ModelForm):
    # Set by RoutingRuleAdmin.get_form to the user editing the rule.
    request_user: Any = None

    class Meta:
        model = RoutingRule
        fields = "__all__"  # noqa: DJ007

    def clean(self) -> dict[str, Any]:
        super().clean()
        user = self.request_user
        if (
            self.cleaned_data.get("pseudonymize") is False
            and user is not None
            and not user.has_perm("router.can_transfer_unpseudonymized")
        ):
            # Only turning pseudonymization off needs the permission: a new rule
            # saved that way, or an existing one flipping from True to False.
            # Editing, enabling or disabling an already-unpseudonymized rule doesn't.
            is_new = self.instance.pk is None
            switched_off = "pseudonymize" in self.changed_data
            if is_new or switched_off:
                self.add_error(
                    "pseudonymize",
                    "You are not allowed to send studies without pseudonymization.",
                )
        return self.cleaned_data


class RoutingRuleAdmin(admin.ModelAdmin):
    form = RoutingRuleAdminForm
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
        form = cast(type[RoutingRuleAdminForm], super().get_form(request, obj, change, **kwargs))
        form.request_user = request.user
        return form

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
