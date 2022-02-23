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
        data = []
        counter = 1
        reader = csv.DictReader(batch_file, delimiter=settings.CSV_DELIMITER)
        for row in reader:
            data_row = {}

            row_empty = True
            for field, column in self.field_to_column_mapping.items():
                value = row.get(column, "").strip()
                if value:
                    row_empty = False
                    data_row[field] = self.transform_value(field, value)

            if row_empty:
                continue

            data_row["task_id"] = counter
            counter += 1

            data_row["lines"] = [reader.line_num]

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

    # Method that can be overridden to adapt the value for a specific field
    # pylint: disable=unused-argument
    def transform_value(self, field: str, value):
        return value
