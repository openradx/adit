from rest_framework import serializers
from adit.core.serializers import BatchTaskSerializer, BatchTaskListSerializer
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

    def validate_pseudonym(self, pseudonym):
        if not pseudonym and not self.can_transfer_unpseudonymized:
            raise serializers.ValidationError("This field is required.")
        return pseudonym
