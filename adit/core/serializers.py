from collections import Counter
import re
from rest_framework import serializers
from django.utils import formats


class DicomTaskListSerializer(
    serializers.ListSerializer
):  # pylint: disable=abstract-method
    row_id_field = "row_number"

    def find_duplicates(self, items):
        return [item for item, count in Counter(items).items() if count > 1]

    def validate(self, attrs):
        attrs = super().validate(attrs)

        row_ids = [data[self.row_id_field] for data in attrs]
        duplicates = self.find_duplicates(row_ids)
        if len(duplicates) > 0:
            ds = ", ".join(str(i) for i in duplicates)
            raise serializers.ValidationError(f"Duplicate 'Row ID': {ds}")

        return attrs


class DicomTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = None
        list_serializer_class = DicomTaskListSerializer

    def __init__(self, instance=None, data=None, **kwargs):
        super().__init__(instance=instance, data=data, **kwargs)
        self.date_input_formats = formats.get_format("DATE_INPUT_FORMATS")

    def adapt_date_field(self, field):
        field.input_formats = self.date_input_formats
        field.error_messages["invalid"] = "Date has wrong format."

    def patient_name_to_dicom(self, patient_name):
        return re.sub(r"\s*,\s*", "^", patient_name)
