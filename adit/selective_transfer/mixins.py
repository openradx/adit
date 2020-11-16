from django.conf import settings
from adit.core.models import TransferTask
from adit.core.templatetags.dicom_helpers import parse_dicom_date
from .models import SelectiveTransferJob


class SelectiveTransferJobCreateMixin:
    def create_source_connector(self, form):
        server = form.instance.source.dicomserver
        return server.create_connector()

    def query_studies(self, connector, form, limit_results):
        data = form.cleaned_data
        studies = connector.find_studies(
            patient_id=data["patient_id"],
            patient_name=data["patient_name"],
            birth_date=data["patient_birth_date"],
            accession_number=data["accession_number"],
            study_date=data["study_date"],
            modality=data["modality"],
            limit_results=limit_results,
            prefer_study_root=True,
        )

        studies = sorted(studies, key=lambda study: study["PatientName"].lower())
        studies = sorted(
            studies,
            key=lambda study: parse_dicom_date(study["StudyDate"]),
            reverse=True,
        )

        return studies

    def transfer_selected_studies(self, user, form, selected_studies):
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
            TransferTask.objects.create(
                job=job,
                patient_id=patient_id,
                study_uid=study_uid,
                pseudonym=pseudonym,
            )

        if user.is_staff or settings.SELECTIVE_TRANSFER_UNVERIFIED:
            job.status = SelectiveTransferJob.Status.PENDING
            job.save()
            job.delay()

        return job
