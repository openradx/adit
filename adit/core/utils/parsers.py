from typing import List, Dict, TextIO
import csv
from rest_framework.exceptions import ErrorDetail
from django.conf import settings
from adit.core.models import DicomTask
from adit.core.serializers import BatchTaskSerializer


class BatchTaskParserError(Exception):
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
                    batch_id = self.data[num].get("batch_id", "").strip()
                    if batch_id:
                        batch_id = f" (Batch ID {batch_id})"

                    line_num = self.data[num]["__line_num__"]

                    self.message += f"Invalid data on line {line_num}{batch_id}:\n"

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


class BatchTaskParser:  # pylint: disable=too-few-public-methods
    def __init__(
        self,
        serializer_class: BatchTaskSerializer,
        field_to_column_mapping: Dict[str, str],
    ) -> None:
        self.serializer_class = serializer_class
        self.field_to_column_mapping = field_to_column_mapping
        self.delimiter = settings.CSV_FILE_DELIMITER

    def parse(self, csv_file: TextIO) -> List[DicomTask]:
        data = []
        reader = csv.DictReader(csv_file, delimiter=self.delimiter)
        for row in reader:
            data_row = {}

            for field, column in self.field_to_column_mapping.items():
                data_row[field] = row.get(column, "")

            data_row["__line_num__"] = reader.line_num

            data.append(data_row)

        serializer = self.serializer_class(  # pylint: disable=not-callable
            data=data, many=True
        )
        if not serializer.is_valid():
            raise BatchTaskParserError(
                self.field_to_column_mapping,
                data,
                serializer.errors,
            )

        model_class = self.serializer_class.Meta.model

        return [model_class(**item) for item in serializer.validated_data]
