from rest_framework import serializers
from adit.core.serializers import BatchTaskSerializer
from .models import BatchTransferTask


class BatchTransferTaskSerializer(BatchTaskSerializer):
    class Meta(BatchTaskSerializer.Meta):
        model = BatchTransferTask
        fields = [
            "batch_id",
            "patient_id",
            "study_uid",
            "pseudonym",
        ]

    def __init__(self, instance, data, **kwargs):
        self.can_transfer_unpseudonymized = kwargs.pop("can_transfer_unpseudonymized")
        super().__init__(instance=instance, data=data, **kwargs)

    def validate_pseudonym(self, pseudonym):
        if not pseudonym and not self.can_transfer_unpseudonymized:
            raise serializers.ValidationError("This field is required.")
