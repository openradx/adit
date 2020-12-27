from adit.core.serializers import BatchTaskSerializer
from .models import BatchFinderQuery


class BatchFinderQuerySerializer(BatchTaskSerializer):
    class Meta(BatchTaskSerializer.Meta):
        model = BatchFinderQuery
        fields = [
            "batch_id",
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
        self.patient_name_to_dicom(data, "patient_name")

        if "modalities" in data:
            modalities = data["modalities"].split(",")
            data["modalities"] = map(str.strip, modalities)

        self.clean_date_string(data, "patient_birth_date")
        self.clean_date_string(data, "study_date_start")
        self.clean_date_string(data, "study_date_end")

        return super().to_internal_value(data)
