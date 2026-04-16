from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from adit.core.models import DicomServer
from adit.core.utils.dicom_operator import DicomOperator
from adit.mass_transfer.processors import DiscoveredSeries, FilterSpec, discover_series


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
        "Discover all distinct studies by running C-FIND queries against a DICOM server "
        "using the given filters and date range. Outputs CSV to stdout or a file. "
        "This is read-only — no database records are created and no files are transferred."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            type=str,
            required=True,
            help="Name of the source DICOM server (as configured in ADIT).",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            required=True,
            help="Start date for study discovery (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            required=True,
            help="End date for study discovery (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--filters",
            type=str,
            required=True,
            help="Path to a JSON file containing a list of filter objects.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="",
            help="Path to write CSV output. If omitted, writes to stdout.",
        )

    def handle(self, *args, **options):
        server_name = options["source"]
        output_path = options["output"]

        try:
            server = DicomServer.objects.get(name=server_name)
        except DicomServer.DoesNotExist:
            raise CommandError(f"DICOM server '{server_name}' not found.")

        try:
            start_date = date.fromisoformat(options["start_date"])
        except ValueError:
            raise CommandError("Invalid --start-date format. Use YYYY-MM-DD.")

        try:
            end_date = date.fromisoformat(options["end_date"])
        except ValueError:
            raise CommandError("Invalid --end-date format. Use YYYY-MM-DD.")

        if end_date < start_date:
            raise CommandError("--end-date must be on or after --start-date.")

        try:
            with open(options["filters"]) as f:
                raw_filters = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise CommandError(f"Failed to read filters file: {e}")

        if not isinstance(raw_filters, list) or not raw_filters:
            raise CommandError("Filters file must contain a non-empty JSON array.")

        filters = [FilterSpec.from_dict(d) for d in raw_filters]

        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time().replace(microsecond=0))

        self.stderr.write(
            f"Discovering studies on '{server_name}' "
            f"from {start_date} to {end_date} ({len(filters)} filter(s))..."
        )

        operator = DicomOperator(server, persistent=True)
        try:
            discovered = discover_series(operator, filters, start, end)
        finally:
            operator.close()

        studies = _aggregate_studies(discovered)
        self.stderr.write(f"Found {len(studies)} distinct study(ies).")

        if output_path:
            with open(output_path, "w", newline="") as f:
                _write_csv(f, studies)
            self.stderr.write(f"CSV written to {output_path}")
        else:
            _write_csv(sys.stdout, studies)


def _aggregate_studies(discovered: list[DiscoveredSeries]) -> dict[str, StudyRecord]:
    studies: dict[str, StudyRecord] = {}
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
    return studies


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
