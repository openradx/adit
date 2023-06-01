from collections import defaultdict
from typing import IO, DefaultDict

from adit.core.parsers import BatchFileParser

from .models import BatchTransferTask
from .serializers import BatchTransferTaskSerializer

mapping = {
    "patient_id": "PatientID",
    "study_uid": "StudyInstanceUID",
    "series_uids": "SeriesInstanceUID",
    "pseudonym": "Pseudonym",
}


class BatchTransferFileParser(BatchFileParser[BatchTransferTask]):
    def __init__(
        self,
        can_transfer_unpseudonymized: bool,
    ) -> None:
        self.can_transfer_unpseudonymized = can_transfer_unpseudonymized
        super().__init__(mapping)

    def get_serializer(self, data: dict[str, str]):
        return BatchTransferTaskSerializer(
            data=data,
            many=True,
            can_transfer_unpseudonymized=self.can_transfer_unpseudonymized,
        )

    def parse(self, batch_file: IO, max_batch_size: int | None) -> list[BatchTransferTask]:
        tasks = super().parse(batch_file, max_batch_size)

        # Tasks with different series of the same study must be grouped together.
        # This is necessary for pseudonymization, so that the whole study
        # (with its series) are processed by one to worker and get the same
        # pseudonymized Study Instance UID.
        tasks_by_study: DefaultDict[str, list[BatchTransferTask]] = defaultdict(list)
        for task in tasks:
            tasks_by_study[task.study_uid].append(task)

        tasks_to_transfer: list[BatchTransferTask] = []
        for index, tasks_with_same_study in enumerate(tasks_by_study.values()):
            transfer_whole_study = False
            selective_series_to_transfer: list[str] = []
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
                task.series_uids = list(set(selective_series_to_transfer))  # type: ignore

            tasks_to_transfer.append(task)

        return tasks_to_transfer

    def transform_value(self, field: str, value):
        # Model field series_uids is a list of Series Instance UIDs, so we
        # have to convert our UIDs to a list first that are later grouped
        # together to the correct study (see above).
        if field == "series_uids":
            return [value]

        return value
