from rest_framework import serializers
from api.serializers import TransferTaskSerializer
from main.models import TransferTask, DicomStudy
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

    def is_valid(self, raise_exception=False):
        print("in valid")
        return super().is_valid(raise_exception=raise_exception)

    def create(self, validated_data):
        print("in create")
        tasks_data = validated_data.pop("tasks")
        print(tasks_data)
        job = SelectiveTransferJob.objects.create(**validated_data)
        for task_data in tasks_data:
            study_list_data = task_data.pop("study_list", [])
            task = TransferTask.objects.create(job=job, **task_data)
            for study_data in study_list_data:
                DicomStudy.objects.create(task=task, **study_data)

        print(job.id)
        return job
