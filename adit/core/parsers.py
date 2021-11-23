from typing import Dict, TextIO, Type
import csv
from django.conf import settings
from .serializers import BatchTaskSerializer
from .errors import BatchFileSizeError, BatchFileFormatError


class BatchFileParser:
    serializer_class: Type[BatchTaskSerializer] = None

    def __init__(self, field_to_column_mapping: Dict[str, str]) -> None:
        self.field_to_column_mapping = field_to_column_mapping

    def get_serializer(self, data: Dict[str, str]) -> BatchTaskSerializer:
        # pylint: disable=not-callable
        return self.serializer_class(data=data, many=True)

    def parse(self, batch_file: TextIO, max_batch_size: int):
        if not "task_id" in self.field_to_column_mapping:
            raise AssertionError("The mapping must contain a 'task_id' field.")

        data = []
        reader = csv.DictReader(batch_file, delimiter=settings.CSV_DELIMITER)

        study_uids = []
        series_uids = []
        for row in reader:
            data_row = {}

            for field, column in self.field_to_column_mapping.items():
                data_row[field] = row.get(column, "")
            if data_row["series_uids"] == "":
                del data_row["series_uids"]
            data_row["__line_num__"] = reader.line_num

            # Skip rows without a task ID
            if not data_row["task_id"]:
                continue
            series_uids.append("series_uids" in data_row)
            study_uids.append(data_row["study_uid"])
            data.append(data_row)
        if any(series_uids):
            study_uids = list(set(study_uids))
            squeezed_data = []
            for study_uid in study_uids:
                tmp_data_row = {}
                for data_row in data:
                    if data_row["study_uid"] == study_uid:
                        if not tmp_data_row:
                            tmp_data_row = data_row
                            series_uid = tmp_data_row["series_uids"]
                            tmp_data_row["series_uids"] = list()
                            tmp_data_row["series_uids"].append(series_uid)
                        else:
                            tmp_data_row["series_uids"].append(data_row["series_uids"])
                squeezed_data.append(tmp_data_row)
            data = squeezed_data
        if max_batch_size is not None and len(study_uids) > max_batch_size:
            raise BatchFileSizeError(len(study_uids), max_batch_size)

        serializer = self.get_serializer(data)
        if not serializer.is_valid():
            raise BatchFileFormatError(
                self.field_to_column_mapping,
                data,
                serializer.errors,
            )

        return serializer.get_tasks()

