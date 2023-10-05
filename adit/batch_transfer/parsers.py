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
        # (with its series) are processed by only one worker and get the same
        # pseudonymized Study Instance UID.
        tasks_by_study: DefaultDict[str, list[BatchTransferTask]] = defaultdict(list)
        for task in tasks:
            tasks_by_study[task.study_uid].append(task)

        tasks_to_transfer: list[BatchTransferTask] = []
        for tasks_with_same_study in tasks_by_study.values():
            transfer_whole_study = False
            explicit_series_to_transfer: list[str] = []
            cumulative_lines = []
            for task in tasks_with_same_study:
                cumulative_lines.extend(task.lines_list)
                if not task.series_uids_list:
                    transfer_whole_study = True
                else:
                    explicit_series_to_transfer.extend(task.series_uids_list)

            task: BatchTransferTask = tasks_with_same_study[0]
            task.lines_list = cumulative_lines

            if transfer_whole_study:
                task.series_uids = ""
            else:
                # Remove duplicates, but keep order
                task.series_uids_list = list(dict.fromkeys(explicit_series_to_transfer))

            tasks_to_transfer.append(task)

        return tasks_to_transfer
