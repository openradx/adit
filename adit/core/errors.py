from datetime import timedelta

from rest_framework.exceptions import ErrorDetail


class DicomError(Exception):
    pass


default_retry_delta = timedelta(minutes=20)


class RetriableDicomError(Exception):
    def __init__(self, message: str, delta: timedelta = default_retry_delta) -> None:
        super().__init__(message)
        self.delta = delta


class BatchFileSizeError(Exception):
    def __init__(self, batch_tasks_count: int, max_batch_size: int) -> None:
        super().__init__("Too many batch tasks.")

        self.batch_tasks_count = batch_tasks_count
        self.max_batch_size = max_batch_size


class BatchFileFormatError(Exception):
    pass


class BatchFileContentError(Exception):
    def __init__(self, mapping, data, errors) -> None:
        super().__init__("Invalid batch data.")

        self.mapping = mapping
        self.data = data
        self.errors = errors

        self.message = None

    def __str__(self) -> str:
        if self.message is None:
            self.build_error_message()

        assert self.message is not None
        return self.message

    def build_error_message(self) -> None:
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
                    lines: str = ", ".join(map(str, self.data[num]["lines"]))
                    lines_label = "lines" if "," in lines else "line"
                    self.message += f"Invalid data on {lines_label} {lines}:\n"

                    non_field_errors = item_errors.pop("non_field_errors", None)
                    if non_field_errors:
                        self._non_field_error_message(non_field_errors)

                    for field_name in item_errors:
                        field_errors = item_errors[field_name]
                        self._field_error_message(field_name, field_errors)

    def _field_error_message(self, field_name: str, field_errors: list[ErrorDetail]) -> None:
        column_name = self.mapping[field_name]
        assert self.message is not None
        self.message += f"{column_name} - "
        self.message += " ".join(field_errors) + "\n"

    def _non_field_error_message(self, non_field_errors: list[ErrorDetail]):
        assert self.message is not None
        self.message += " ".join(non_field_errors) + "\n"
