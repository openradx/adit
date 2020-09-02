from rest_framework import serializers
from rest_framework.fields import empty
from adit.main.models import DicomNode, TransferJob, TransferTask


class DicomNodeSerializer(serializers.ModelSerializer):
    node_type = serializers.CharField(source="get_node_type_display")

    class Meta:
        model = DicomNode
        fields = ["node_name", "node_type"]


class TransferTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransferTask
        fields = ["patient_id", "study_uid", "series_uids", "pseudonym"]

    def __init__(self, instance=None, data=empty, max_series_count=100, **kwargs):
        self.max_series_count = max_series_count
        super().__init__(instance=instance, data=data, **kwargs)

    def validate_series_uids(self, series_uids):  # pylint: disable=no-self-use
        # TODO validate the series UID itself
        if len(series_uids) > self.max_series_count:
            raise serializers.ValidationError(
                f"Maximum {self.max_series_count} series per task allowed."
            )
        return series_uids


class TransferJobListSerializer(serializers.ModelSerializer):
    source = DicomNodeSerializer()
    destination = DicomNodeSerializer()
    status = serializers.CharField(source="get_status_display")
    job_type = serializers.CharField(source="get_job_type_display")

    class Meta:
        model = TransferJob
        fields = [
            "id",
            "source",
            "destination",
            "job_type",
            "status",
            "message",
            "trial_protocol_id",
            "trial_protocol_name",
            "created_by",
            "created_at",
            "started_at",
            "stopped_at",
        ]
