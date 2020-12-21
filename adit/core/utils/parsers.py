import re
from datetime import datetime
from collections import Counter


class ParserError(Exception):
    pass


class BaseParser:
    item_name = None
    field_to_column_mapping = None

    def __init__(self, delimiter, date_formats):
        self.delimiter = delimiter
        self.date_formats = date_formats

    def parse_int(self, value):
        value = value.strip()
        if value.isdigit():
            return int(value)
        return value

    def parse_string(self, value):
        return value.strip()

    def parse_name(self, value):
        value = value.strip()
        return re.sub(r"\s*,\s*", "^", value)

    def parse_date(self, value):
        value = value.strip()
        if value == "":
            return None
        for date_format in self.date_formats:
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                pass
        return value

    def build_item_error(self, message_dict, row_number, item_number):
        general_errors = []
        field_errors = []

        if not isinstance(row_number, int):
            row_number = None

        if row_number is not None:
            general_errors.append(f"Invalid {self.item_name} [Row {row_number}]:")
        else:
            general_errors.append(f"Invalid {self.item_name} [#{item_number + 1}]:")

        for field_id, messages in message_dict.items():
            if field_id == "__all__":
                for message in messages:
                    general_errors.append(message)
            else:
                column_label = self.field_to_column_mapping[field_id]
                field_errors.append(f"{column_label}: {', '.join(messages)}")

        return "\n".join(general_errors) + "\n" + "\n".join(field_errors) + "\n"

    def find_duplicates(self, items):
        return [item for item, count in Counter(items).items() if count > 1]
