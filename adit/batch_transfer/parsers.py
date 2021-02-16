from typing import Dict
from adit.core.parsers import BatchFileParser
from adit.core.serializers import BatchTaskSerializer
from .serializers import BatchTransferTaskSerializer


class BatchTransferFileParser(BatchFileParser):
    def __init__(
        self,
        field_to_column_mapping: Dict[str, str],
        can_transfer_unpseudonymized: bool,
    ) -> None:
        self.can_transfer_unpseudonymized = can_transfer_unpseudonymized
        super().__init__(field_to_column_mapping)

    def get_serializer(self, data: Dict[str, str]) -> BatchTaskSerializer:
        return BatchTransferTaskSerializer(
            data=data,
            many=True,
            can_transfer_unpseudonymized=self.can_transfer_unpseudonymized,
        )
