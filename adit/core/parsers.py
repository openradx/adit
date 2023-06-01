from abc import ABC
from typing import IO, Generic, Type, TypeVar, cast

import numpy as np
import pandas as pd

from .errors import BatchFileContentError, BatchFileFormatError, BatchFileSizeError
from .models import DicomTask
from .serializers import BatchTaskListSerializer, BatchTaskSerializer

T = TypeVar("T", bound=DicomTask)


class BatchFileParser(Generic[T], ABC):
    serializer_class: Type[BatchTaskSerializer] | None = None

    def __init__(self, field_to_column_mapping: dict[str, str]) -> None:
        self.field_to_column_mapping = field_to_column_mapping

    def get_serializer(self, data: list[dict[str, str]]) -> BatchTaskListSerializer:
        if not self.serializer_class:
            raise ValueError("Unknown serializer class.")
        # many=True automatically returns the list serializer
        return cast(BatchTaskListSerializer, self.serializer_class(data=data, many=True))

    def parse(self, batch_file: IO, max_batch_size: int | None) -> list[T]:
        data: list[dict[str, str]] = []
        counter = 1

        try:
            df = pd.read_excel(batch_file, dtype=str)
        except ValueError:
            raise BatchFileFormatError()

        df.replace({np.nan: ""}, inplace=True)
        for idx, (_, row) in enumerate(df.iterrows()):
            data_row = {}

            row_empty = True
            for field, column in self.field_to_column_mapping.items():
                value = str(row.get(column, "")).strip()
                if value:
                    row_empty = False
                    data_row[field] = self.transform_value(field, value)

            if row_empty:
                continue

            data_row["task_id"] = counter
            counter += 1

            # + 2 because the first row is the header and the index starts at 0
            data_row["lines"] = [idx + 2]

            data.append(data_row)

        if max_batch_size is not None and len(data) > max_batch_size:
            raise BatchFileSizeError(len(data), max_batch_size)

        serializer = self.get_serializer(data)

        if not serializer.is_valid():
            raise BatchFileContentError(
                self.field_to_column_mapping,
                data,
                serializer.errors,
            )

        return serializer.get_tasks()

    # Method that can be overridden to adapt the value for a specific field
    def transform_value(self, field: str, value):
        return value
