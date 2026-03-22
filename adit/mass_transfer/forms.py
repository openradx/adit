from __future__ import annotations

import json
import secrets
from typing import Annotated, cast

from adit_radis_shared.accounts.models import User
from codemirror.widgets import CodeMirror
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Field, Layout, Row, Submit
from django import forms
from django.core.exceptions import ValidationError
from pydantic import BaseModel, model_validator
from pydantic import ValidationError as PydanticValidationError

from adit.core.fields import DicomNodeChoiceField
from adit.core.models import DicomNode

from .models import MassTransferJob, MassTransferTask
from .utils.partitions import build_partitions


class FilterSchema(BaseModel):
    """Pydantic model for validating mass transfer filter JSON objects."""

    modality: str = ""
    institution_name: str = ""
    apply_institution_on_study: bool = True
    study_description: str = ""
    series_description: str = ""
    series_number: int | None = None
    min_age: Annotated[int, "non-negative"] | None = None
    max_age: Annotated[int, "non-negative"] | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def check_age_range(self):
        if self.min_age is not None and self.min_age < 0:
            raise ValueError("min_age must be non-negative")
        if self.max_age is not None and self.max_age < 0:
            raise ValueError("max_age must be non-negative")
        if (
            self.min_age is not None
            and self.max_age is not None
            and self.min_age > self.max_age
        ):
            raise ValueError(f"min_age ({self.min_age}) cannot exceed max_age ({self.max_age})")
        return self


FILTERS_JSON_EXAMPLE = json.dumps(
    [
        {
            "modality": "MR",
            "institution_name": "Neuroradiologie",
            "study_description": "",
            "series_description": "",
            "series_number": None,
            "apply_institution_on_study": True,
            "min_age": 18,
            "max_age": 90,
        }
    ],
    indent=2,
)


class MassTransferJobForm(forms.ModelForm):
    filters_json = forms.CharField(
        label="Filters (JSON)",
        initial=FILTERS_JSON_EXAMPLE,
        widget=CodeMirror(mode={"name": "javascript", "json": True}),
        help_text=(
            "A JSON array of filter objects. Each filter can have: "
            "modality, institution_name, apply_institution_on_study, "
            "study_description, series_description, series_number, "
            "min_age, max_age. A series matching ANY filter is included."
        ),
    )

    pseudonym_salt = forms.CharField(
        label="Pseudonym salt",
        required=False,
        help_text=(
            "Deterministic seed for pseudonymization."
            " Same salt + same patient ID = same pseudonym."
        ),
        widget=forms.TextInput(attrs={
            "class": "form-control",
        }),
    )

    tasks: list[MassTransferTask]

    class Meta:
        model = MassTransferJob
        fields = (
            "source",
            "destination",
            "start_date",
            "end_date",
            "partition_granularity",
            "pseudonymize",
            "pseudonym_salt",
            "trial_protocol_id",
            "trial_protocol_name",
            "convert_to_nifti",
            "send_finished_mail",
        )
        labels = {
            "start_date": "Start date",
            "end_date": "End date",
            "partition_granularity": "Partition granularity",
            "pseudonymize": "Pseudonymize",
            "pseudonym_salt": "Pseudonym salt",
            "convert_to_nifti": "Convert to NIfTI",
            "send_finished_mail": "Send Email when job is finished",
        }
        help_texts = {
            "partition_granularity": "Daily or weekly partition windows.",
            "pseudonym_salt": (
                "To ensure that patients with the same patient ID receive "
                "the same pseudonyms, just keep the pre-filled salt. "
                "If you want to maintain the same pseudonym for the same "
                "patient ID across different jobs, be sure to reuse the "
                "same salt from previous jobs (by pasting it here). "
                "However, if you wish to pseudonymize each study "
                "independently without retaining the association between "
                "patient IDs and pseudonyms, remove the salt "
                "(leave the field blank)."
            ),
            "convert_to_nifti": (
                "When enabled, exported DICOM series are converted to NIfTI format "
                "using dcm2niix."
            ),
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        self.tasks = []
        self.save_tasks = None
        self.user: User = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        # Auto-populate salt with a fresh random value
        if not self.initial.get("pseudonym_salt"):
            self.initial["pseudonym_salt"] = secrets.token_hex()

        self.fields["source"] = DicomNodeChoiceField("source", self.user)
        self.fields["source"].widget.attrs["@change"] = "onSourceChange($event)"

        self.fields["destination"] = DicomNodeChoiceField("destination", self.user)
        self.fields["destination"].widget.attrs["@change"] = "onDestinationChange($event)"

        self.fields["partition_granularity"].widget.attrs["@change"] = (
            "onGranularityChange($event)"
        )

        self.fields["pseudonymize"].widget.attrs["x-model"] = "pseudonymize"

        self.fields["send_finished_mail"].widget.attrs["@change"] = (
            "onSendFinishedMailChange($event)"
        )

        self.helper = FormHelper(self)
        self.helper.layout = Layout(
            Div(
                HTML("<div class='card-header fw-semibold'>Transfer scope</div>"),
                Div(
                    Row(
                        Column(Field("source"), css_class="col-md-6"),
                        Column(Field("destination"), css_class="col-md-6"),
                        css_class="g-3",
                    ),
                    Row(
                        Column(Field("start_date"), css_class="col-md-6"),
                        Column(Field("end_date"), css_class="col-md-6"),
                        css_class="g-3",
                    ),
                    Row(
                        Column(Field("partition_granularity"), css_class="col-md-6"),
                        Column(Field("pseudonymize"), css_class="col-md-6"),
                        css_class="g-3",
                    ),
                    Div(
                        Field("pseudonym_salt"),
                        css_id="salt-wrapper",
                        **{"x-show": "showSalt"},
                    ),
                    Row(
                        Column(Field("convert_to_nifti"), css_class="col-md-6"),
                        Column(Field("send_finished_mail"), css_class="col-md-6"),
                        css_class="g-3",
                    ),
                    css_class="card-body",
                ),
                css_class="card mb-3",
            ),
            Div(
                HTML("<div class='card-header fw-semibold'>Filters</div>"),
                Div(
                    Field("filters_json"),
                    css_class="card-body",
                ),
                css_class="card mb-3",
            ),
        )
        self.helper.render_unmentioned_fields = False
        self.helper.attrs["x-data"] = "massTransferJobForm()"
        self.helper.add_input(Submit("save", "Create Job"))

    def clean_source(self):
        source = cast(DicomNode, self.cleaned_data["source"])
        if not source.is_accessible_by_user(self.user, "source"):
            raise ValidationError("You do not have access to this source.")
        if source.node_type != DicomNode.NodeType.SERVER:
            raise ValidationError("Source must be a DICOM server.")
        return source

    def clean_destination(self):
        destination = cast(DicomNode, self.cleaned_data["destination"])
        if not destination.is_accessible_by_user(self.user, "destination"):
            raise ValidationError("You do not have access to this destination.")
        if destination.node_type != DicomNode.NodeType.FOLDER:
            raise ValidationError("Destination must be a DICOM folder.")
        return destination

    def clean(self):
        cleaned = super().clean()
        assert cleaned is not None
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise ValidationError("End date must be on or after the start date.")
        return cleaned

    def clean_filters_json(self):
        raw = self.cleaned_data["filters_json"].strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON: {e}")

        if not isinstance(data, list) or not data:
            raise ValidationError("Filters must be a non-empty JSON array.")

        validated: list[dict] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                raise ValidationError(f"Filter #{i + 1} must be a JSON object.")
            try:
                fs = FilterSchema(**item)
                validated.append(fs.model_dump(exclude_none=True))
            except PydanticValidationError as e:
                errors = "; ".join(err["msg"] for err in e.errors())
                raise ValidationError(f"Filter #{i + 1}: {errors}")

        return validated

    def _save_tasks(self, job: MassTransferJob) -> None:
        partitions = build_partitions(
            job.start_date,
            job.end_date,
            job.partition_granularity,
        )

        tasks: list[MassTransferTask] = []
        for partition in partitions:
            tasks.append(
                MassTransferTask(
                    job=job,
                    source=job.source,
                    partition_start=partition.start,
                    partition_end=partition.end,
                    partition_key=partition.key,
                )
            )

        MassTransferTask.objects.bulk_create(tasks)

    def save(self, commit: bool = True):
        job = super().save(commit=False)
        job.urgent = False
        job.filters_json = self.cleaned_data["filters_json"]

        if commit:
            job.save()
            self._save_tasks(job)
        else:
            self.save_tasks = self._save_tasks

        return job
