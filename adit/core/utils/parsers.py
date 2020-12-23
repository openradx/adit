from django.conf import settings


class ParserError(Exception):
    pass


class BaseParser:  # pylint: disable=too-few-public-methods
    item_name = None
    field_to_column_mapping = None

    def __init__(self):
        self.delimiter = settings.CSV_FILE_DELIMITER

    def build_error_message(self, errors, data):
        message = ""

        if isinstance(errors, dict):
            for error in errors["non_field_errors"]:
                message += f"{error}.\n"

        if isinstance(errors, list):
            for num, error in enumerate(errors):
                if message:
                    message += "\n"
                if error:
                    for field in error:
                        row_number = data[num].get("row_number")
                        if row_number:
                            message += f"Invalid data in Row {row_number}:\n"
                        else:
                            message += f"Invalid data in row {num}:\n"
                        column = self.field_to_column_mapping[field]
                        message += f"{column} - {error[field]}"

        return message
