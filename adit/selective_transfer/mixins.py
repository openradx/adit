from datetime import datetime

from django.conf import settings

from adit.core.utils.dicom_connector import DicomConnector

from .models import SelectiveTransferJob, SelectiveTransferTask


class SelectiveTransferJobCreateMixin:
    def create_source_connector(self, form):
        return DicomConnector(form.instance.source.dicomserver)

    def query_studies(self, connector, form, limit_results):
        data = form.cleaned_data

        if data["modality"] in settings.EXCLUDED_MODALITIES:
            return []

        studies = connector.find_studies(
            {
                "PatientID": data["patient_id"],
                "PatientName": data["patient_name"],
                "PatientBirthDate": data["patient_birth_date"],
                "AccessionNumber": data["accession_number"],
                "StudyDate": data["study_date"],
                "ModalitiesInStudy": data["modality"],
                "StudyInstanceUID": "",
                "StudyDescription": "",
                "StudyTime": "",
                "NumberOfStudyRelatedInstances": "",
            },
            limit_results=limit_results,
        )

        def contains_not_excluded_modality(study):
            if "ModalitiesInStudy" not in study:
                return False

            modalities_in_study = set(study["ModalitiesInStudy"])
            excluded_modalities = set(settings.EXCLUDED_MODALITIES)
            not_excluded_modalities = list(modalities_in_study - excluded_modalities)
            return len(not_excluded_modalities) > 0

        studies = [study for study in studies if contains_not_excluded_modality(study)]

        studies = sorted(studies, key=lambda study: study["PatientName"].lower())
        studies = sorted(
            studies,
            key=lambda study: datetime.combine(study["StudyDate"], study["StudyTime"]),
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
        for idx, selected_study in enumerate(selected_studies):
            study_data = selected_study.split("\\")
            patient_id = study_data[0]
            study_uid = study_data[1]
            SelectiveTransferTask.objects.create(
                job=job,
                task_id=idx + 1,
                patient_id=patient_id,
                study_uid=study_uid,
                pseudonym=pseudonym,
            )

        if user.is_staff or settings.SELECTIVE_TRANSFER_UNVERIFIED:
            job.status = SelectiveTransferJob.Status.PENDING
            job.save()
            job.delay()

        return job
