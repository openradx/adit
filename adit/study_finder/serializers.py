from adit.core.serializers import DicomTaskSerializer
from .models import StudyFinderQuery


class StudyFinderQuerySerializer(DicomTaskSerializer):
    class Meta:
        model = StudyFinderQuery
        fields = [
            "row_number",
            "patient_id",
            "patient_name",
            "patient_birth_date",
            "study_date_start",
            "study_date_end",
            "modalities",
        ]

    def __init__(self, instance=None, data=None, **kwargs):
        super().__init__(instance, data, **kwargs)

        self.adapt_date_field("patient_birth_date")
        self.adapt_date_field("study_date_start")
        self.adapt_date_field("study_date_end")

    def to_internal_value(self, data):
        if "patient_name" in data:
            data["patient_name"] = self.patient_name_to_dicom(data["patient_name"])

        if "modalities" in data:
            modalities = data["modalities"].split(",")
            data["modalities"] = map(str.strip, modalities)

        return super().to_internal_value(data)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # In contrast to Django's ModelForm does a ModelSerializer not call
        # the model clean method itself (at leat in DRF v3).
        query = StudyFinderQuery(**attrs)
        query.clean()

        return attrs
