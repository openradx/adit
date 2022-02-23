from collections import defaultdict
from typing import Dict, TextIO
from adit.core.parsers import BatchFileParser
from adit.core.serializers import BatchTaskSerializer
from .models import BatchTransferTask
from .serializers import BatchTransferTaskSerializer

mapping = {
    "patient_id": "PatientID",
    "study_uid": "StudyInstanceUID",
    "pseudonym": "Pseudonym",
    "series_uids": "SeriesInstanceUID",
}


class BatchTransferFileParser(BatchFileParser):
    def __init__(
        self,
        can_transfer_unpseudonymized: bool,
    ) -> None:
        self.can_transfer_unpseudonymized = can_transfer_unpseudonymized
        super().__init__(mapping)

    def get_serializer(self, data: Dict[str, str]) -> BatchTaskSerializer:
        return BatchTransferTaskSerializer(
            data=data,
            many=True,
            can_transfer_unpseudonymized=self.can_transfer_unpseudonymized,
        )

    def parse(self, batch_file: TextIO, max_batch_size: int):
        tasks: list[BatchTransferTask] = super().parse(batch_file, max_batch_size)

        # Tasks with different series of same study must be grouped togehter.
        # This is even necessary for pseudonymization that all the series get
        # the same pseudonymized Study Instance UID.
        tasks_by_study = defaultdict(list)
        for task in tasks:
            tasks_by_study[task.study_uid].append(task)

        tasks_to_transfer = []
        for index, tasks_with_same_study in enumerate(tasks_by_study.values()):
            transfer_whole_study = False
            selective_series_to_transfer = []
            lines_in_batch_file = []
            for task in tasks_with_same_study:
                lines_in_batch_file.extend(task.lines)
                if task.series_uids is None:
                    transfer_whole_study = True
                else:
                    selective_series_to_transfer.extend(task.series_uids)

            task: BatchTransferTask = tasks_with_same_study[0]
            task.task_id = index + 1
            task.lines = lines_in_batch_file

            if transfer_whole_study:
                task.series_uids = None
            else:
                task.series_uids = list(set(selective_series_to_transfer))

            tasks_to_transfer.append(task)

        return tasks_to_transfer

    def transform_value(self, field: str, value):
        if field == "series_uids":
            return [value]

        return value
