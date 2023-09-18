from datetime import datetime
from typing import Iterator

from django.conf import settings

from adit.accounts.models import User
from adit.core.mixins import LockedMixin
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_operator import DicomOperator

from .apps import SECTION_NAME
from .forms import SelectiveTransferJobForm
from .models import SelectiveTransferJob, SelectiveTransferSettings, SelectiveTransferTask


class SelectiveTransferLockedMixin(LockedMixin):
    settings_model = SelectiveTransferSettings
    section_name = SECTION_NAME


class SelectiveTransferJobCreateMixin:
    """A mixin shared by the "SelectiveTransferJobCreateView and the SelectiveTransferConsumer.

    It contains common logic to create a selective transfer job. The view has some rudimentary
    functionality to make a query, display the result and create the job. The consumer
    does this more interactively and is the preferred way, but depends on JavaScript and
    WebSockets. The view is a fallback for browsers without JavaScript support.
    TODO: As more and more things inside ADIT now depend on JavaScript, we should consider
    to remove the view logic to query and create a job from the view and only use the consumer.
    The view then just renders the initial form and the consumer does the rest.
    """

    def create_source_operator(self, form: SelectiveTransferJobForm) -> DicomOperator:
        return DicomOperator(form.cleaned_data["source"].dicomserver)

    def query_studies(
        self, operator: DicomOperator, form: SelectiveTransferJobForm, limit_results: int
    ) -> Iterator[ResultDataset]:
        data = form.cleaned_data

        if data["modality"] in settings.EXCLUDED_MODALITIES:
            return []

        studies = operator.find_studies(
            QueryDataset.create(
                PatientID=data["patient_id"],
                PatientName=data["patient_name"],
                PatientBirthDate=data["patient_birth_date"],
                AccessionNumber=data["accession_number"],
                StudyDate=data["study_date"],
                ModalitiesInStudy=data["modality"],
            ),
            limit_results=limit_results,
        )

        def has_only_excluded_modalities(study: ResultDataset):
            modalities_in_study = set(study.ModalitiesInStudy)
            excluded_modalities = set(settings.EXCLUDED_MODALITIES)
            not_excluded_modalities = list(modalities_in_study - excluded_modalities)
            return len(not_excluded_modalities) == 0

        for study in studies:
            if has_only_excluded_modalities(study):
                continue

            yield study

    def sort_studies(self, studies: list[ResultDataset]) -> list[ResultDataset]:
        return sorted(
            studies,
            key=lambda study: datetime.combine(study.StudyDate, study.StudyTime),
            reverse=True,
        )

    def transfer_selected_studies(
        self, user: User, form: SelectiveTransferJobForm, selected_studies: list[str]
    ) -> SelectiveTransferJob:
        if not selected_studies:
            raise ValueError("At least one study to transfer must be selected.")
        if len(selected_studies) > 10 and not user.is_staff:
            raise ValueError("Maximum 10 studies per selective transfer are allowed.")

        form.instance.owner = user
        job = form.save()

        pseudonym = form.cleaned_data["pseudonym"]
        for selected_study in selected_studies:
            study_data = selected_study.split("\\")
            patient_id = study_data[0]
            study_uid = study_data[1]
            SelectiveTransferTask.objects.create(
                job=job,
                source=form.cleaned_data["source"],
                destination=form.cleaned_data["destination"],
                patient_id=patient_id,
                study_uid=study_uid,
                pseudonym=pseudonym,
            )

        if user.is_staff or settings.SELECTIVE_TRANSFER_UNVERIFIED:
            job.status = SelectiveTransferJob.Status.PENDING
            job.save()
            job.delay()

        return job
