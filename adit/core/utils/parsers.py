from typing import List
from django.conf import settings
from rest_framework.exceptions import ErrorDetail


class ParserError(Exception):
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
                    row_id = self.data[num].get("row_id", "").strip()
                    if row_id:
                        row_id = f" (Row ID {row_id})"

                    # +2 because row begins at 1 and the first line is the header
                    self.message += f"Invalid data in row #{num + 2}{row_id}:\n"

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


class BaseParser:  # pylint: disable=too-few-public-methods
    def __init__(self):
        self.delimiter = settings.CSV_FILE_DELIMITER
