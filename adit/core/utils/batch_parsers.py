from typing import List, Dict, TextIO, Type
import csv
from rest_framework.exceptions import ErrorDetail
from django.conf import settings
from adit.core.models import DicomTask
from adit.core.serializers import BatchTaskSerializer


def parse_csv_file(
    serializer_class: Type[BatchTaskSerializer],
    field_to_column_mapping: Dict[str, str],
    csv_file: TextIO,
    extra_serializer_params=None,
) -> List[DicomTask]:
    if not "batch_id" in field_to_column_mapping:
        raise AssertionError("The mapping must contain a 'batch_id' field.")

    data = []
    reader = csv.DictReader(csv_file, delimiter=settings.CSV_FILE_DELIMITER)
    for row in reader:
        data_row = {}

        for field, column in field_to_column_mapping.items():
            data_row[field] = row.get(column, "")

        data_row["__line_num__"] = reader.line_num

        data.append(data_row)

    if extra_serializer_params:
        serializer = serializer_class(data=data, many=True, **extra_serializer_params)
    else:
        serializer = serializer_class(data=data, many=True)

    if not serializer.is_valid():
        raise ParsingError(
            field_to_column_mapping,
            data,
            serializer.errors,
        )

    model_class = serializer_class.Meta.model

    return [model_class(**item) for item in serializer.validated_data]


class ParsingError(Exception):
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
                        batch_id = f" (BatchID {batch_id})"

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
