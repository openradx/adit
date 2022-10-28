from rest_framework import serializers
from django.utils import formats


class BatchTaskListSerializer(
    serializers.ListSerializer
):  # pylint: disable=abstract-method
    def __init__(self, *args, **kwargs):
        self.model = kwargs.pop("model")
        super().__init__(*args, **kwargs)

    def get_tasks(self):
        return [self.model(**item) for item in self.validated_data]


class BatchTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = None
        fields = None
        list_serializer_class = BatchTaskListSerializer

    @classmethod
    def many_init(cls, *args, **kwargs):
        kwargs["child"] = cls()
        kwargs["model"] = cls.Meta.model
        return BatchTaskListSerializer(*args, **kwargs)

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

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # In contrast to Django's ModelForm does a ModelSerializer not call
        # the model clean method itself (at leat in DRF v3), so we must do
        # this manually
        batch_task = self.Meta.model(**attrs)  # pylint: disable=not-callable
        batch_task.clean()

        return attrs
