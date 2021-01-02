from collections import Counter
import re
from rest_framework import serializers
from django.utils import formats


class BatchTaskListSerializer(
    serializers.ListSerializer
):  # pylint: disable=abstract-method
    def find_duplicates(self, items):
        return [item for item, count in Counter(items).items() if count > 1]

    def validate(self, attrs):
        attrs = super().validate(attrs)

        batch_ids = [data["batch_id"] for data in attrs]
        duplicates = self.find_duplicates(batch_ids)
        if len(duplicates) > 0:
            ds = ", ".join(str(i) for i in duplicates)
            raise serializers.ValidationError(f"Duplicate 'Batch ID': {ds}")

        return attrs


class BatchTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = None
        list_serializer_class = BatchTaskListSerializer

    def __init__(self, instance=None, data=None, **kwargs):
        super().__init__(instance=instance, data=data, **kwargs)
        self.date_input_formats = formats.get_format("DATE_INPUT_FORMATS")

    def adapt_date_field(self, field_name):
        field = self.fields[field_name]
        field.input_formats = self.date_input_formats
        field.error_messages["invalid"] = "Date has wrong format."

    def clean_date_string(self, data, field_name):
        if field_name in data:
            data[field_name] = data[field_name].strip()
            if data[field_name] == "":
                data[field_name] = None

    def patient_name_to_dicom(self, data, field_name):
        if field_name in data:
            data[field_name] = re.sub(r"\s*,\s*", "^", data[field_name])

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # In contrast to Django's ModelForm does a ModelSerializer not call
        # the model clean method itself (at leat in DRF v3).
        batch_task = self.model(**attrs)
        batch_task.clean()

        return attrs
