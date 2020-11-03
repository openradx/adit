from adit.main.models import TransferTask


class SelectiveTransferJobCreateMixin:
    def do_query(self, form):
        data = form.cleaned_data
        server = form.instance.source.dicomserver
        connector = server.create_connector()
        studies = connector.find_studies(
            patient_id=data["patient_id"],
            patient_name=data["patient_name"],
            birth_date=data["patient_birth_date"],
            accession_number=data["accession_number"],
            study_date=data["study_date"],
            modality=data["modality"],
            limit_results=50,
        )
        return studies

    def do_transfer(self, user, form, selected_studies):
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

        return job
