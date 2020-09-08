from rest_framework import serializers
from adit.main.serializers import TransferTaskSerializer
from adit.main.models import DicomNode, TransferTask

from .models import SelectiveTransferJob


class SelectiveTransferJobCreateSerializer(serializers.ModelSerializer):
    tasks = TransferTaskSerializer(many=True)

    class Meta:
        model = SelectiveTransferJob
        fields = [
            "id",
            "source",
            "destination",
            "trial_protocol_id",
            "trial_protocol_name",
            "archive_password",
            "tasks",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].error_messages["null"] = "This field is required."
        self.fields["destination"].error_messages["null"] = "This field is required."

    def validate_source(self, source):
        if source.node_type != DicomNode.NodeType.SERVER:
            raise serializers.ValidationError("Must be a DICOM server.")

        if not source.active:
            raise serializers.ValidationError("Is not active.")

        return source

    def validate_destination(self, destination):
        if not destination.active:
            raise serializers.ValidationError("Is not active.")

    def create(self, validated_data):
        tasks_data = validated_data.pop("tasks")
        job = SelectiveTransferJob.objects.create(**validated_data)
        for task_data in tasks_data:
            TransferTask.objects.create(job=job, **task_data)

        return job
