from rest_framework import serializers

from adit.core.serializers import BatchTaskListSerializer, BatchTaskSerializer

from .models import BatchTransferTask


class BatchTransferTaskListSerializer(BatchTaskListSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)

        # Check that the same study_uid belongt to only one patient_id
        study_uid_to_patient_id = {}
        for data in attrs:
            study_uid = data["study_uid"]
            patient_id = data["patient_id"]
            if study_uid not in study_uid_to_patient_id:
                study_uid_to_patient_id[study_uid] = patient_id
            if study_uid_to_patient_id[study_uid] != patient_id:
                raise serializers.ValidationError(
                    f"Same Study Instance UID {study_uid} can't belong to different Patient IDs."
                )

        # Check that the same patient_id only has one pseudonym
        patient_id_to_pseudonym = {}
        for data in attrs:
            patient_id = data["patient_id"]
            pseudonym = data["pseudonym"]
            if patient_id not in patient_id_to_pseudonym:
                patient_id_to_pseudonym[patient_id] = pseudonym
            if patient_id_to_pseudonym[patient_id] != pseudonym:
                raise serializers.ValidationError(
                    f"Same Patient ID {patient_id} can't have different pseudonyms."
                )

        return attrs


class BatchTransferTaskSerializer(BatchTaskSerializer):
    class Meta(BatchTaskSerializer.Meta):
        model = BatchTransferTask
        fields = [
            "task_id",  # TODO: still needed?
            "patient_id",
            "study_uid",
            "pseudonym",
            "series_uids",
        ]
        list_serializer_class = BatchTransferTaskListSerializer

    @classmethod
    def many_init(cls, *args, **kwargs):
        # We can't use the many_init classmethod of BatchTaskSerializer as we need to
        # provide can_transfer_unpseudonymized to BatchTransferTaskSerializer, but not to
        # BatchTaskListSerializer (otherwise we would an unexpected argument error there).
        kwargs["child"] = cls(*args, **kwargs)
        del kwargs["can_transfer_unpseudonymized"]
        kwargs["model"] = cls.Meta.model
        return BatchTaskListSerializer(*args, **kwargs)

    def __init__(self, instance=None, data=None, **kwargs):
        self.can_transfer_unpseudonymized = kwargs.pop("can_transfer_unpseudonymized")
        super().__init__(instance=instance, data=data, **kwargs)

    def validate(self, attrs):
        data = super().validate(attrs)

        if not self.can_transfer_unpseudonymized and not data.get("pseudonym", ""):
            raise serializers.ValidationError(
                {"pseudonym": "You are only allowed to transfer pseudonymized."}
            )

        return data
