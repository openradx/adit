from adit.core.serializers import BatchTaskSerializer

from .models import BatchQueryTask


class BatchQueryTaskSerializer(BatchTaskSerializer):
    class Meta(BatchTaskSerializer.Meta):
        model = BatchQueryTask
        fields = [
            "patient_id",
            "patient_name",
            "patient_birth_date",
            "accession_number",
            "study_date_start",
            "study_date_end",
            "modalities",
            "study_description",
            "series_description",
            "series_numbers",
            "pseudonym",
        ]

    def __init__(self, instance=None, data=None, **kwargs):
        super().__init__(instance, data, **kwargs)

        self.adapt_date_field("patient_birth_date")
        self.adapt_date_field("study_date_start")
        self.adapt_date_field("study_date_end")
