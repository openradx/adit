import logging
from typing import cast

from django.apps import apps

from adit_server.core.utils.model_utils import get_model_label

from ..models import DicomTask
from ..processors import DicomTaskProcessor
from ..site import dicom_processors

logger = logging.getLogger(__name__)


def get_dicom_task(model_label: str, task_id: int) -> DicomTask:
    DicomTaskModel = cast(DicomTask, apps.get_model(model_label))
    return DicomTaskModel.objects.get(id=task_id)


def get_dicom_processor(dicom_task: DicomTask) -> DicomTaskProcessor:
    processor_class = dicom_processors[get_model_label(dicom_task.__class__)]
    return processor_class(dicom_task)
