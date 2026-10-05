"""Delivers the series a routing rule selected from a router batch."""

import tempfile
from pathlib import Path

from django.conf import settings

from adit.core.errors import DicomError
from adit.core.models import DicomNode, DicomTask
from adit.core.processors import DicomTaskProcessor
from adit.core.types import ProcessingResult
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import read_dataset, write_dataset
from adit.core.utils.presentation_contexts import requested_store_contexts
from adit.core.utils.pseudonymizer import Pseudonymizer

from .models import RouterSettings, RouterTask
from .utils import spool
from .utils.batches import read_series_images

_FORWARD_AGAIN = "The PACS has to forward the study again."


class RouterTaskProcessor(DicomTaskProcessor):
    app_name = "router"
    dicom_task_class = RouterTask
    app_settings_class = RouterSettings

    def __init__(self, dicom_task: DicomTask) -> None:
        assert isinstance(dicom_task, RouterTask)
        super().__init__(dicom_task)
        self.router_task = dicom_task

    def process(self) -> ProcessingResult:
        task = self.router_task
        job = task.job
        batch = job.batch
        if batch.files_deleted_at:
            raise DicomError(f"The images were deleted from the router spool. {_FORWARD_AGAIN}")

        batch_path = spool.batch_dir(
            Path(settings.ROUTER_SPOOL_PATH), batch.sender_id, batch.batch_id
        )
        if not batch_path.is_dir():
            raise DicomError(f"The batch folder {batch_path} is missing. {_FORWARD_AGAIN}")

        already_sent = RouterTask.already_sent(job.rule_id, task.study_uid, task.destination_id)
        try:
            images = [
                image
                for image in read_series_images(batch_path, set(task.series_uids))
                if image.sop_instance_uid not in already_sent
            ]
        except FileNotFoundError as err:
            raise DicomError(f"A batch file is missing. {_FORWARD_AGAIN}") from err
        if not images:
            return {
                "status": RouterTask.Status.SUCCESS,
                "message": "Nothing new to send.",
                "log": "",
            }

        destination = task.destination
        assert destination.node_type == DicomNode.NodeType.SERVER
        if task.pseudonym:
            manipulator = DicomManipulator(Pseudonymizer(seed=job.rule.pseudonym_salt))
        else:
            manipulator = DicomManipulator()

        with tempfile.TemporaryDirectory(prefix="adit_router_") as tmpdir:
            pairs: set[tuple[str, str]] = set()
            try:
                for image in images:
                    ds = read_dataset(image.path)
                    manipulator.manipulate(
                        ds,
                        pseudonym=task.pseudonym or None,
                        trial_protocol_id=job.trial_protocol_id or None,
                        trial_protocol_name=job.trial_protocol_name or None,
                    )
                    pairs.add((str(ds.SOPClassUID), str(ds.file_meta.TransferSyntaxUID)))
                    write_dataset(ds, Path(tmpdir) / f"{image.sop_instance_uid}.dcm")
            except FileNotFoundError as err:
                raise DicomError(f"A batch file is missing. {_FORWARD_AGAIN}") from err

            operator = DicomOperator(
                destination.dicomserver, store_contexts=requested_store_contexts(pairs)
            )
            operator.upload_images(Path(tmpdir))

        sent = sorted(image.sop_instance_uid for image in images)
        # The runner saves only the fields it owns, so this survives the end of the task.
        RouterTask.objects.filter(pk=task.pk).update(sent_instance_uids=sent)
        return {
            "status": RouterTask.Status.SUCCESS,
            "message": f"Sent {len(sent)} images to {destination.name}.",
            "log": "",
        }
