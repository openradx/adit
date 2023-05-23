from datetime import timedelta
from typing import List

from rest_framework.exceptions import ErrorDetail


class RetriableTaskError(Exception):
    def __init__(self, message: str, long_delay: bool = False) -> None:
        if long_delay:
            self.delay = timedelta(hours=24)
        else:
            self.delay = timedelta(minutes=15)

        super().__init__(message)


class BatchFileSizeError(Exception):
    def __init__(self, batch_tasks_count: int, max_batch_size: int) -> None:
        super().__init__("Too many batch tasks.")

        self.batch_tasks_count = batch_tasks_count
        self.max_batch_size = max_batch_size

class BatchFileFormatError(Exception):
    pass

class BatchFileContentError(Exception):
    def __init__(self, field_to_column_mapping, data, errors) -> None:
        super().__init__("Invalid batch data.")

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
                    lines = ", ".join([str(line) for line in self.data[num]["lines"]])
                    self.message += f"Invalid data on line(s) {lines}:\n"

                    non_field_errors = item_errors.pop("non_field_errors", None)
                    if non_field_errors:
                        self._non_field_error_message(non_field_errors)

                    for field_name in item_errors:
                        field_errors = item_errors[field_name]
                        self._field_error_message(field_name, field_errors)

    def _field_error_message(self, field_name: str, field_errors: List[ErrorDetail]) -> None:
        column_name = self.field_to_column_mapping[field_name]
        self.message += f"{column_name} - "
        self.message += " ".join(field_errors) + "\n"

    def _non_field_error_message(self, non_field_errors: List[ErrorDetail]):
        self.message += " ".join(non_field_errors) + "\n"
