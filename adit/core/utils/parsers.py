import re
from datetime import datetime


class BaseParser:
    def __init__(self, delimiter, date_formats):
        self._delimiter = delimiter
        self._date_formats = date_formats

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
        for date_format in self._date_formats:
            try:
                return datetime.strptime(value, date_format)
            except ValueError:
                pass
        return value
