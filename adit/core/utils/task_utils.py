import io
import logging
from typing import Tuple

from ..models import DicomTask

logger = logging.getLogger(__name__)


def hijack_logger(my_logger) -> Tuple[logging.StreamHandler, io.StringIO]:
    """Intercept all logger messages to save them later to the task."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    my_logger.parent.addHandler(handler)
    return handler, stream


def store_log_in_task(
    my_logger: logging.Logger,
    handler: logging.StreamHandler,
    stream: io.StringIO,
    dicom_task: DicomTask,
) -> None:
    handler.flush()
    if dicom_task.log:
        dicom_task.log += "\n" + stream.getvalue()
    else:
        dicom_task.log = stream.getvalue()
    stream.close()
    my_logger.parent.removeHandler(handler)
