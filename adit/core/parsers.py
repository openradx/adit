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
        for row in reader:
            data_row = {}

            for field, column in self.field_to_column_mapping.items():
                data_row[field] = row.get(column, "")

            data_row["__line_num__"] = reader.line_num

            # Skip rows without a task ID
            if not data_row["task_id"]:
                continue

            data.append(data_row)

        if max_batch_size is not None and len(data) > max_batch_size:
            raise BatchFileSizeError(len(data), max_batch_size)

        serializer = self.get_serializer(data)

        if not serializer.is_valid():
            raise BatchFileFormatError(
                self.field_to_column_mapping,
                data,
                serializer.errors,
            )

        return serializer.get_tasks()
