from rest_framework import serializers
from adit.main.serializers import TransferTaskSerializer
from adit.main.models import DicomNode, TransferTask

from .models import SelectiveTransferJob


class SelectiveTransferJobCreateSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="transfer_job_detail")
    tasks = TransferTaskSerializer(many=True)

    class Meta:
        model = SelectiveTransferJob
        fields = [
            "id",
            "url",
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

    def validate_source(self, source):  # pylint: disable=no-self-use
        if source.node_type != DicomNode.NodeType.SERVER:
            raise serializers.ValidationError("Must be a DICOM server.")

        if not source.active:
            raise serializers.ValidationError("Is not active.")

        return source

    def validate_destination(self, destination):  # pylint: disable=no-self-use
        if not destination.active:
            raise serializers.ValidationError("Is not active.")

        return destination

    def validate_tasks(self, tasks):  # pylint: disable=no-self-use
        if len(tasks) == 0:
            raise serializers.ValidationError(
                "For the transfer at least one item must be selected."
            )

        user = self.context["request"].user

        if len(tasks) > 10 and not user.is_staff:
            raise serializers.ValidationError(
                "Maximum 10 items per transfer can be selected."
            )

        return tasks

    def create(self, validated_data):
        tasks_data = validated_data.pop("tasks")
        job = SelectiveTransferJob.objects.create(**validated_data)
        for task_data in tasks_data:
            TransferTask.objects.create(job=job, **task_data)

        return job
