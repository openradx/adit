from django.core import exceptions
from rest_framework import serializers
from rest_framework.fields import empty

from adit.core.models import DicomNode, TransferJob, TransferTask
from adit.core.validators import validate_uids


class DicomNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DicomNode
        fields = ["name"]


class TransferTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferTask
        fields = ["patient_id", "study_uid", "series_uids", "pseudonym"]

    def __init__(self, instance=None, data=empty, max_series_count=100, **kwargs):
        self.max_series_count = max_series_count
        super().__init__(instance=instance, data=data, **kwargs)

    def validate_series_uids(self, series_uids):
        try:
            validate_uids(series_uids)
        except exceptions.ValidationError as err:
            raise serializers.ValidationError(err.message)

        series_uid_list = list(filter(len, map(str.strip, series_uids.split(","))))
        if len(series_uid_list) > self.max_series_count:
            raise serializers.ValidationError(
                f"Maximum {self.max_series_count} series per task allowed."
            )

        return series_uids


class TransferJobListSerializer(serializers.ModelSerializer):
    source = DicomNodeSerializer()
    destination = DicomNodeSerializer()
    status = serializers.CharField(source="get_status_display")

    class Meta:
        model = TransferJob
        fields = [
            "id",
            "source",
            "destination",
            "status",
            "message",
            "trial_protocol_id",
            "trial_protocol_name",
            "owner",
            "created",
            "start",
            "end",
        ]
