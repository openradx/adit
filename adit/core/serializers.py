from typing import Type

from rest_framework import serializers

from adit.core.models import DicomTask


class BatchTaskListSerializer(serializers.ListSerializer):
    def __init__(self, *args, **kwargs):
        self.model = kwargs.pop("model")
        super().__init__(*args, **kwargs)

    def get_tasks(self):
        assert isinstance(self.validated_data, list)
        return [self.model(**item) for item in self.validated_data]


class BatchTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model: Type[DicomTask]
        fields: list[str]
        list_serializer_class = BatchTaskListSerializer

    @classmethod
    def many_init(cls, *args, **kwargs):
        kwargs["child"] = cls()
        kwargs["model"] = cls.Meta.model
        return BatchTaskListSerializer(*args, **kwargs)

    def adapt_date_field(self, field_name):
        field = self.fields[field_name]
        field.error_messages["invalid"] = "Date has wrong format."

    def validate(self, attrs):
        attrs = super().validate(attrs)

        # In contrast to Django's ModelForm does a ModelSerializer not call
        # the model clean method itself (at leat in DRF v3), so we must do
        # this manually
        batch_task = self.Meta.model(**attrs)
        batch_task.clean()

        return attrs
