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
