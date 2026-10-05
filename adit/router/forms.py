import json
from typing import Any

from adit_radis_shared.accounts.models import User
from codemirror.widgets import CodeMirror
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from django import forms
from django.forms.fields import InvalidJSONInput

from .models import RoutingRule

FILTERS_EXAMPLE = [
    {"mode": "include", "modality": "CT", "min_age": 20, "max_age": 30},
    {"mode": "exclude", "series_description": "*localizer*"},
]

FILTERS_HELP_TEXT = (
    "A JSON array of filter objects. Each filter can have: mode ('include' or 'exclude', "
    "default 'include'), modality, institution_name, apply_institution_on_study, "
    "study_description, series_description, series_number, min_age, max_age and "
    "min_number_of_series_related_instances. A series is sent when it matches an include "
    "filter and no exclude filter; at least one include filter is required. String criteria "
    "support the DICOM wildcards * and ? and must match the whole value: case-sensitively "
    "on include filters, case-insensitively on exclude filters. The Help button explains "
    "more."
)

LOCKED_HELP_TEXT = "Fixed once the rule has sent studies. Create a new rule to change it."


class FiltersJSONField(forms.JSONField):
    def prepare_value(self, value: Any) -> Any:
        # Indented, so the editor shows the filters the way staff write them.
        if isinstance(value, InvalidJSONInput):
            return value
        return json.dumps(value, indent=2, ensure_ascii=False, cls=self.encoder)


class RoutingRuleForm(forms.ModelForm):
    """The routing rule form of the router pages, also used by the Django admin."""

    filters_json = FiltersJSONField(
        label="Filters (JSON)",
        widget=CodeMirror(mode={"name": "javascript", "json": True}),
        help_text=FILTERS_HELP_TEXT,
    )

    class Meta:
        model = RoutingRule
        fields = (
            "name",
            "enabled",
            "destination",
            "filters_json",
            "pseudonymize",
            "pseudonym_salt",
            "trial_protocol_id",
            "trial_protocol_name",
        )
        labels = {"trial_protocol_id": "Trial protocol ID"}
        help_texts = {
            "enabled": "Only enabled rules route the studies that arrive.",
            "pseudonym_salt": (
                "The same salt gives a patient the same pseudonym. Keep the pre-filled salt, "
                "or paste the salt of a mass transfer job to give its patients the same "
                "pseudonyms."
            ),
        }

    def __init__(self, *args: Any, user: User, **kwargs: Any) -> None:
        self.user = user
        super().__init__(*args, **kwargs)

        if self.instance.pk is None and self.initial.get("filters_json") is None:
            self.initial["filters_json"] = FILTERS_EXAMPLE

        if self.instance.pk is not None and self.instance.jobs.exists():
            # A patient must keep the same pseudonym under a rule. Disabled fields ignore
            # what is posted for them.
            for name in ("pseudonymize", "pseudonym_salt"):
                # The Django admin shows these two as read-only fields instead.
                if name in self.fields:
                    self.fields[name].disabled = True
                    self.fields[name].help_text = LOCKED_HELP_TEXT

        self.helper = FormHelper()
        self.helper.add_input(Submit("save", "Save Rule"))

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        assert cleaned_data is not None
        if cleaned_data.get("pseudonymize") is False and not self.user.has_perm(
            "router.can_transfer_unpseudonymized"
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
        return cleaned_data
