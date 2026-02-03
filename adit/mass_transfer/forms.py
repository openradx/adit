from __future__ import annotations

from typing import cast

from adit_radis_shared.accounts.models import User
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit
from django import forms
from django.core.exceptions import ValidationError

from adit.core.fields import DicomNodeChoiceField
from adit.core.models import DicomNode

from .models import MassTransferFilter, MassTransferJob, MassTransferTask
from .utils.partitions import build_partitions


class MassTransferFilterForm(forms.ModelForm):
    class Meta:
        model = MassTransferFilter
        fields = (
            "name",
            "modality",
            "institution_name",
            "apply_institution_on_study",
            "study_description",
            "series_description",
            "series_number",
        )
        labels = {
            "name": "Filter name",
            "modality": "Modality",
            "institution_name": "Institution name",
            "apply_institution_on_study": "Apply institution filter on study",
            "study_description": "Study description",
            "series_description": "Series description",
            "series_number": "Series number",
        }


class MassTransferJobForm(forms.ModelForm):
    filters = forms.ModelMultipleChoiceField(
        queryset=MassTransferFilter.objects.all(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
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
            "filters",
            "pseudonymize",
            "send_finished_mail",
        )
        labels = {
            "start_date": "Start date",
            "end_date": "End date",
            "partition_granularity": "Partition granularity",
            "pseudonymize": "Pseudonymize data",
            "send_finished_mail": "Send Email when job is finished",
        }
        help_texts = {
            "partition_granularity": "Daily or weekly partition windows.",
            "pseudonymize": (
                "When disabled, patient identifiers are preserved and output folders use "
                "Patient ID."
            ),
        }

    def __init__(self, *args, **kwargs):
        self.tasks = []
        self.save_tasks = None
        self.user: User = kwargs.pop("user")

        super().__init__(*args, **kwargs)

        self.fields["source"] = DicomNodeChoiceField("source", self.user)
        self.fields["source"].widget.attrs["@change"] = "onSourceChange($event)"

        self.fields["destination"] = DicomNodeChoiceField("destination", self.user)
        self.fields["destination"].widget.attrs["@change"] = "onDestinationChange($event)"

        self.fields["partition_granularity"].widget.attrs["@change"] = (
            "onGranularityChange($event)"
        )

        self.fields["send_finished_mail"].widget.attrs["@change"] = (
            "onSendFinishedMailChange($event)"
        )

        self.helper = FormHelper(self)
        self.helper.layout = Layout("source", "destination")
        self.helper.render_unmentioned_fields = True
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
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise ValidationError("End date must be on or after the start date.")
        return cleaned

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
        # Mass transfer always converts to NIfTI
        job.convert_to_nifti = True
        job.urgent = False

        if commit:
            job.save()
            self.save_m2m()
            self._save_tasks(job)
        else:
            self.save_tasks = self._save_tasks

        return job
