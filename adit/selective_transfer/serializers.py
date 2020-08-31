from rest_framework import serializers
from adit.api.serializers import TransferTaskSerializer
from adit.main.models import TransferTask
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

    def create(self, validated_data):
        tasks_data = validated_data.pop("tasks")
        job = SelectiveTransferJob.objects.create(**validated_data)
        for task_data in tasks_data:
            TransferTask.objects.create(job=job, **task_data)

        return job
