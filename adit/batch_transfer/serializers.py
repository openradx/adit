from adit.core.serializers import DicomTaskSerializer
from .models import BatchTransferRequest


class BatchTransferRequestSerializer(DicomTaskSerializer):
    class Meta:
        model = BatchTransferRequest
        fields = [
            "row_id",
            "patient_id",
            "patient_name",
            "patient_birth_date",
            "accession_number",
            "study_date",
            "modality",
            "pseudonym",
        ]

    def __init__(self, instance=None, data=None, **kwargs):
        super().__init__(instance, data, **kwargs)

        self.adapt_date_field("patient_birth_date")
        self.adapt_date_field("study_date")

    def to_internal_value(self, data):
        if "patient_name" in data:
            data["patient_name"] = self.patient_name_to_dicom(data["patient_name"])

        return super().to_internal_value(data)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # In contrast to Django's ModelForm does a ModelSerializer not call
        # the model clean method itself (at leat in DRF v3).
        request = BatchTransferRequest(**attrs)
        request.clean()

        return attrs
