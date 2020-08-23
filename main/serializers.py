from rest_framework import serializers
from rest_framework.fields import empty
from .models import DicomNode, TransferJob, TransferTask, DicomStudy


class DicomNodeSerializer(serializers.ModelSerializer):
    node_type = serializers.CharField(source="get_node_type_display")

    class Meta:
        model = DicomNode
        fields = ["node_name", "node_type"]


class DicomStudySerializer(serializers.ModelSerializer):
    class Meta:
        model = DicomStudy
        fields = ["patient_id", "study_uid", "modalities", "pseudonym"]


class TransferTaskSerializer(serializers.ModelSerializer):
    study_list = DicomStudySerializer(many=True)

    class Meta:
        model = TransferTask
        fields = ["study_list"]

    def __init__(self, instance=None, data=empty, max_study_count=3, **kwargs):
        self.max_study_count = max_study_count
        super().__init__(instance=instance, data=data, **kwargs)

    def validate_study_list(self, study_list):  # pylint: disable=no-self-use
        print("validating study_list")
        print(study_list)
        if len(study_list) > 3:
            raise serializers.ValidationError(
                f"Maximum {self.max_study_count} studies per task allowed."
            )
        return study_list

    def create(self, validated_data):
        study_list_data = validated_data.pop("study_list")
        task = TransferTask.objects.create(**validated_data)
        for study_data in study_list_data:
            DicomStudy.objects.create(task=task, **study_data)
        return task


class TransferJobCreateSerializer(serializers.ModelSerializer):
    tasks = TransferTaskSerializer(many=True)

    class Meta:
        model = TransferJob
        fields = [
            "source",
            "destination",
            "trial_protocol_id",
            "trial_protocol_name",
            "archive_password",
            "tasks",
        ]

    def create(self, validated_data):
        tasks_data = validated_data.pop("tasks")
        job = TransferJob.objects.create(**validated_data)
        for task_data in tasks_data:
            TransferTask.objects.create(job=job, **task_data)
        return job


class TransferJobDetailSerializer(serializers.ModelSerializer):
    tasks = TransferTaskSerializer(many=True)
    archive = serializers.BooleanField(source="is_transfer_to_archive")

    class Meta:
        model = TransferJob
        fields = [
            "source",
            "destination",
            "trial_protocol_id",
            "trial_protocol_name",
            "archive",
            "tasks",
        ]


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
