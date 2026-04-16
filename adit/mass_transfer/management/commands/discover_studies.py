from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from adit.core.utils.dicom_operator import DicomOperator
from adit.mass_transfer.models import MassTransferJob
from adit.mass_transfer.processors import DiscoveredSeries, MassTransferTaskProcessor


@dataclass
class StudyRecord:
    """Aggregated study-level record for CSV output."""

    study_instance_uid: str
    patient_id: str
    accession_number: str
    study_description: str
    study_datetime: datetime
    modalities: set[str]


CSV_COLUMNS = [
    "study_instance_uid",
    "patient_id",
    "accession_number",
    "study_description",
    "study_datetime",
    "modalities",
]


class Command(BaseCommand):
    help = (
        "Discover all distinct studies for a MassTransferJob by running C-FIND queries "
        "against the source DICOM server. Outputs CSV to stdout or a file. "
        "This is read-only — no database records are created and no files are transferred."
    )

    def add_arguments(self, parser):
        parser.add_argument("job_id", type=int, help="ID of the MassTransferJob.")
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="Path to write CSV output. If omitted, writes to stdout.",
        )

    def handle(self, *args, **options):
        job_id = options["job_id"]
        output_path = options["output"]

        try:
            job = MassTransferJob.objects.get(pk=job_id)
        except MassTransferJob.DoesNotExist:
            raise CommandError(f"MassTransferJob with ID {job_id} does not exist.")

        filters = job.get_filters()
        if not filters:
            raise CommandError(f"Job {job_id} has no filters configured.")

        tasks = list(job.tasks.order_by("partition_start"))
        if not tasks:
            raise CommandError(f"Job {job_id} has no tasks (partitions).")

        source_node = tasks[0].source
        if source_node.node_type != source_node.NodeType.SERVER:
            raise CommandError("Mass transfer source must be a DICOM server.")

        self.stderr.write(
            f"Discovering studies for job {job_id} "
            f"({len(tasks)} partition(s), {len(filters)} filter(s))..."
        )

        studies: dict[str, StudyRecord] = {}
        operator = DicomOperator(source_node.dicomserver, persistent=True)

        try:
            for i, task in enumerate(tasks, 1):
                self.stderr.write(
                    f"  Partition {i}/{len(tasks)}: {task.partition_key} "
                    f"({task.partition_start} to {task.partition_end})"
                )
                processor = MassTransferTaskProcessor(task)
                discovered = processor._discover_series(operator, filters)
                self._aggregate_studies(studies, discovered)
        finally:
            operator.close()

        self.stderr.write(f"Found {len(studies)} distinct study(ies).")

        if output_path:
            with open(output_path, "w", newline="") as f:
                self._write_csv(f, studies)
            self.stderr.write(f"CSV written to {output_path}")
        else:
            self._write_csv(sys.stdout, studies)

    @staticmethod
    def _aggregate_studies(
        studies: dict[str, StudyRecord],
        discovered: list[DiscoveredSeries],
    ) -> None:
        for series in discovered:
            uid = series.study_instance_uid
            if uid in studies:
                studies[uid].modalities.add(series.modality)
            else:
                studies[uid] = StudyRecord(
                    study_instance_uid=uid,
                    patient_id=series.patient_id,
                    accession_number=series.accession_number,
                    study_description=series.study_description,
                    study_datetime=series.study_datetime,
                    modalities={series.modality},
                )

    @staticmethod
    def _write_csv(file, studies: dict[str, StudyRecord]) -> None:
        writer = csv.writer(file)
        writer.writerow(CSV_COLUMNS)
        for record in sorted(studies.values(), key=lambda r: r.study_datetime):
            writer.writerow(
                [
                    record.study_instance_uid,
                    record.patient_id,
                    record.accession_number,
                    record.study_description,
                    record.study_datetime.isoformat(),
                    ",".join(sorted(record.modalities)),
                ]
            )
