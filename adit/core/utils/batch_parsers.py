from typing import List, Dict, TextIO, Type
import csv
from rest_framework.exceptions import ErrorDetail
from django.conf import settings
from adit.core.serializers import BatchTaskSerializer


class BatchFileParser:
    serializer_class: Type[BatchTaskSerializer] = None

    def __init__(self, field_to_column_mapping: Dict[str, str]) -> None:
        self.field_to_column_mapping = field_to_column_mapping

    def get_serializer(self, data: Dict[str, str]) -> BatchTaskSerializer:
        # pylint: disable=not-callable
        return self.serializer_class(data=data, many=True)

    def parse(self, csv_file: TextIO, max_batch_size: int):
        if not "task_id" in self.field_to_column_mapping:
            raise AssertionError("The mapping must contain a 'task_id' field.")

        data = []
        reader = csv.DictReader(csv_file, delimiter=settings.CSV_FILE_DELIMITER)
        for row in reader:
            data_row = {}

            for field, column in self.field_to_column_mapping.items():
                data_row[field] = row.get(column, "")

            data_row["__line_num__"] = reader.line_num

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


class BatchFileSizeError(Exception):
    def __init__(self, batch_tasks_count: int, max_batch_size: int) -> None:
        super().__init__("Too many batch tasks.")

        self.batch_tasks_count = batch_tasks_count
        self.max_batch_size = max_batch_size


class BatchFileFormatError(Exception):
    def __init__(self, field_to_column_mapping, data, errors) -> None:
        super().__init__("Invalid CSV data.")

        self.field_to_column_mapping = field_to_column_mapping
        self.data = data
        self.errors = errors

        self.message = None

    def __str__(self) -> str:
        if self.message is None:
            self.build_error_message()

        return self.message

    def build_error_message(self) -> str:
        self.message = ""

        if isinstance(self.errors, dict):
            # Comes from the list serializer (when all items itself are valid)
            for error in self.errors["non_field_errors"]:
                self.message += f"{error}.\n"

        if isinstance(self.errors, list):
            # Comes from the item serializer with parameter many=True
            for num, item_errors in enumerate(self.errors):
                if self.message:
                    self.message += "\n"
                if item_errors:
                    task_id = self.data[num].get("task_id", "").strip()
                    line_num = self.data[num]["__line_num__"]

                    self.message += f"Invalid data on line {line_num}"

                    if task_id:
                        self.message += f" (TaskID {task_id})"

                    self.message += ":\n"

                    non_field_errors = item_errors.pop("non_field_errors", None)
                    if non_field_errors:
                        self._non_field_error_message(non_field_errors)

                    for field_name in item_errors:
                        field_errors = item_errors[field_name]
                        self._field_error_message(field_name, field_errors)

    def _field_error_message(
        self, field_name: str, field_errors: List[ErrorDetail]
    ) -> None:
        column_name = self.field_to_column_mapping[field_name]
        self.message += f"{column_name} - "
        self.message += " ".join(field_errors) + "\n"

    def _non_field_error_message(self, non_field_errors: List[ErrorDetail]):
        self.message += " ".join(non_field_errors) + "\n"
