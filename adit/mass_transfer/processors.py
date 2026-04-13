from __future__ import annotations

import json
import logging
import secrets
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import cast

import pydicom
from django.conf import settings
from django.utils import timezone
from pydicom import Dataset
from pydicom.errors import InvalidDicomError

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomNode, DicomTask
from adit.core.processors import DicomTaskProcessor
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import convert_to_python_regex, write_dataset
from adit.core.utils.pseudonymizer import Pseudonymizer, compute_pseudonym
from adit.core.utils.sanitize import sanitize_filename

from .models import (
    MassTransferJob,
    MassTransferSettings,
    MassTransferTask,
    MassTransferVolume,
)


@dataclass(frozen=True)
class FilterSpec:
    """Unified filter representation used by the processor.

    Built from a plain dict from the job's filters_json field.
    """

    modality: str = ""
    institution_name: str = ""
    apply_institution_on_study: bool = True
    study_description: str = ""
    series_description: str = ""
    series_number: int | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_number_of_series_related_instances: int | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "FilterSpec":
        return cls(
            modality=d.get("modality", ""),
            institution_name=d.get("institution_name", ""),
            apply_institution_on_study=d.get("apply_institution_on_study", True),
            study_description=d.get("study_description", ""),
            series_description=d.get("series_description", ""),
            series_number=d.get("series_number"),
            min_age=d.get("min_age"),
            max_age=d.get("max_age"),
            min_number_of_series_related_instances=d.get("min_number_of_series_related_instances"),
        )


logger = logging.getLogger(__name__)

_MIN_SPLIT_WINDOW = timedelta(minutes=30)
_DELAY_BETWEEN_SERIES = 0.5  # seconds between fetch requests to avoid overwhelming the PACS

# Deterministic pseudonyms use 14 characters. Random pseudonyms use 15 so the
# two modes can be distinguished by length.
_DETERMINISTIC_PSEUDONYM_LENGTH = 14
_RANDOM_PSEUDONYM_LENGTH = 15


@dataclass(frozen=True)
class DiscoveredSeries:
    patient_id: str
    accession_number: str
    study_instance_uid: str
    series_instance_uid: str
    modality: str
    study_description: str
    series_description: str
    series_number: int | None
    study_datetime: datetime
    institution_name: str
    number_of_images: int
    patient_birth_date: date | None = None


def _dicom_match(pattern: str, value: str | None) -> bool:
    if not pattern:
        return True
    if value is None:
        return False
    regex = convert_to_python_regex(pattern)
    return bool(regex.search(str(value)))


def _short_error_reason(error: str) -> str:
    lines = [line.strip() for line in error.strip().splitlines() if line.strip()]
    return lines[-1] if lines else error


def _parse_int(value: object, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(cast(str, value))
    except (TypeError, ValueError):
        return default


def _study_datetime(study: ResultDataset) -> datetime:
    study_date = study.StudyDate
    study_time = study.StudyTime
    if study_time is None:
        study_time = datetime.min.time()
    return datetime.combine(study_date, study_time)


def _study_folder_name(study_description: str, study_dt: datetime) -> str:
    desc = sanitize_filename(study_description or "Undefined")
    dt_str = study_dt.strftime("%Y%m%d_%H%M%S")
    return f"{desc}_{dt_str}"


def _series_folder_name(series_description: str, series_number: int | None, series_uid: str) -> str:
    desc = sanitize_filename(series_description or "Undefined")
    if series_number is None:
        return f"{desc}_{sanitize_filename(series_uid)}"
    return f"{desc}_{series_number}"


def _extract_dicom_metadata(dicom_dir: Path) -> dict[str, str]:
    """Read the first DICOM file in *dicom_dir* and extract metadata fields.

    These are post-pseudonymization values — shifted dates, replaced UIDs,
    etc. The function also computes a ``PatientAgeAtStudy`` field from
    PatientBirthDate and StudyDate when both are present.
    """
    for dcm_path in sorted(dicom_dir.glob("*.dcm")):
        try:
            ds = pydicom.dcmread(dcm_path, stop_before_pixels=True)
        except (InvalidDicomError, OSError) as exc:
            logger.warning("Skipping unreadable DICOM file %s: %s", dcm_path, exc)
            continue
        fields: dict[str, str] = {}
        for tag in settings.DICOM_METADATA_TAGS:
            val = ds.get(tag)
            if val is not None:
                fields[tag] = str(val)

        # Compute age at study from birth date and study date
        birth_str = fields.get("PatientBirthDate", "")
        study_str = fields.get("StudyDate", "")
        if len(birth_str) == 8 and len(study_str) == 8:
            try:
                bd = date(int(birth_str[:4]), int(birth_str[4:6]), int(birth_str[6:8]))
                sd = date(int(study_str[:4]), int(study_str[4:6]), int(study_str[6:8]))
                fields["PatientAgeAtStudy"] = str(_age_at_study(bd, sd))
            except (ValueError, OverflowError):
                pass

        return fields
    return {}


def _merge_dicom_metadata(output_path: Path, fields: dict[str, str]) -> None:
    """Merge extra DICOM metadata into dcm2niix JSON sidecars.

    The *fields* are written first and then overlaid with the existing
    dcm2niix values so that dcm2niix-derived fields always take precedence.
    """
    if not fields:
        return
    for sidecar_path in sorted(output_path.glob("*.json")):
        try:
            existing = json.loads(sidecar_path.read_text())
            merged = {**fields, **existing}
            sidecar_path.write_text(json.dumps(merged, indent=2))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            logger.warning("Failed to merge metadata into %s", sidecar_path, exc_info=True)


def _age_at_study(birth_date: date, study_date: date) -> int:
    """Return the patient's age in whole years on the study date."""
    age = study_date.year - birth_date.year
    if (study_date.month, study_date.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def _birth_date_range(
    study_start: date,
    study_end: date,
    min_age: int | None,
    max_age: int | None,
) -> tuple[date, date] | None:
    """Compute a PatientBirthDate range for study queries from age bounds.

    Uses the widest possible range: someone who is max_age on the earliest
    study date was born at the latest on study_start - max_age years, and
    someone who is min_age on the latest study date was born at the earliest
    on study_end - min_age years.  We widen by 1 year on each side to account
    for birthday boundary effects and let client-side filtering be exact.
    """
    if min_age is None and max_age is None:
        return None

    # Earliest possible birth date: max_age on the earliest study day
    if max_age is not None:
        earliest_birth = date(study_start.year - max_age - 1, 1, 1)
    else:
        earliest_birth = date(1900, 1, 1)

    # Latest possible birth date: min_age on the latest study day
    if min_age is not None:
        latest_birth = date(study_end.year - min_age + 1, 12, 31)
    else:
        latest_birth = study_end

    return (earliest_birth, latest_birth)


def _destination_base_dir(node: DicomNode, job: MassTransferJob) -> Path:
    assert node.node_type == DicomNode.NodeType.FOLDER
    name = sanitize_filename(
        f"adit_{job._meta.app_label}_{job.pk}_{job.created.strftime('%Y%m%d')}_{job.owner.username}"
    )
    path = Path(node.dicomfolder.path) / name
    path.mkdir(parents=True, exist_ok=True)
    return path


class MassTransferTaskProcessor(DicomTaskProcessor):
    app_name = "mass_transfer"
    dicom_task_class = MassTransferTask
    app_settings_class = MassTransferSettings

    def __init__(self, dicom_task: DicomTask) -> None:
        assert isinstance(dicom_task, MassTransferTask)
        super().__init__(dicom_task)
        self.mass_task = dicom_task

    def process(self):
        if self.is_suspended():
            return {
                "status": MassTransferTask.Status.WARNING,
                "message": "Mass transfer is currently suspended.",
                "log": "Task skipped because the mass transfer app is suspended.",
            }

        job = self.mass_task.job
        source_node = self.mass_task.source
        destination_node = self.mass_task.destination

        if source_node.node_type != DicomNode.NodeType.SERVER:
            raise DicomError("Mass transfer source must be a DICOM server.")
        if destination_node.node_type not in (DicomNode.NodeType.FOLDER, DicomNode.NodeType.SERVER):
            raise DicomError("Mass transfer destination must be a DICOM folder or server.")

        dest_operator: DicomOperator | None = None
        output_base: Path | None = None
        if destination_node.node_type == DicomNode.NodeType.SERVER:
            dest_operator = DicomOperator(destination_node.dicomserver)
        else:
            assert destination_node.node_type == DicomNode.NodeType.FOLDER
            output_base = _destination_base_dir(destination_node, job)

        try:
            filters = job.get_filters()

            if not filters:
                return {
                    "status": MassTransferTask.Status.FAILURE,
                    "message": "No filters configured for this job.",
                    "log": "Mass transfer requires at least one filter.",
                }

            # Clean up on retry
            if output_base:
                partition_path = output_base / self.mass_task.partition_key
                if partition_path.exists():
                    shutil.rmtree(partition_path)

            MassTransferVolume.objects.filter(
                job=job,
                partition_key=self.mass_task.partition_key,
            ).delete()

            pseudonymizer: Pseudonymizer | None = None
            if job.pseudonymize and job.pseudonym_salt:
                pseudonymizer = Pseudonymizer(seed=job.pseudonym_salt)
            elif job.pseudonymize:
                pseudonymizer = Pseudonymizer()

            operator = DicomOperator(source_node.dicomserver, persistent=True)

            # Discovery: query the source server for all matching series
            discovered = self._discover_series(operator, filters)
            operator.close()

            # Create PENDING volumes so they appear in the UI immediately
            volumes = self._create_pending_volumes(discovered, job, pseudonymizer)
            grouped_volumes = self._group_volumes(volumes)

            # Transfer: fetch series grouped by study
            return self._transfer_grouped_series(
                operator,
                grouped_volumes,
                job,
                pseudonymizer,
                output_base,
                dest_operator,
            )
        finally:
            if dest_operator:
                dest_operator.close()

    def _create_pending_volumes(
        self,
        discovered: list[DiscoveredSeries],
        job: MassTransferJob,
        pseudonymizer: Pseudonymizer | None,
    ) -> list[MassTransferVolume]:
        """Bulk-create PENDING volumes for all discovered series.

        Handles all three pseudonym modes:
        - Deterministic (linked): same patient always gets same pseudonym.
        - Random: per-study random pseudonym.
        - No pseudonymization: pseudonym left empty.
        """
        deterministic_ids: dict[str, str] = {}
        random_pseudonyms: dict[str, str] = {}

        volumes = []
        for series in discovered:
            pid = series.patient_id
            study_uid = series.study_instance_uid

            if pseudonymizer and job.pseudonym_salt:
                if pid not in deterministic_ids:
                    deterministic_ids[pid] = compute_pseudonym(
                        job.pseudonym_salt, pid, length=_DETERMINISTIC_PSEUDONYM_LENGTH
                    )
                pseudonym = deterministic_ids[pid]
            elif pseudonymizer:
                if study_uid not in random_pseudonyms:
                    random_seed = secrets.token_hex(16)
                    random_pseudonyms[study_uid] = compute_pseudonym(
                        random_seed, pid, length=_RANDOM_PSEUDONYM_LENGTH
                    )
                pseudonym = random_pseudonyms[study_uid]
            else:
                pseudonym = ""

            volumes.append(
                MassTransferVolume(
                    job_id=job.pk,
                    task_id=self.mass_task.pk,
                    partition_key=self.mass_task.partition_key,
                    patient_id=series.patient_id,
                    pseudonym=pseudonym,
                    accession_number=series.accession_number,
                    study_instance_uid=series.study_instance_uid,
                    series_instance_uid=series.series_instance_uid,
                    modality=series.modality,
                    study_description=series.study_description,
                    series_description=series.series_description,
                    series_number=series.series_number,
                    study_datetime=timezone.make_aware(series.study_datetime),
                    institution_name=series.institution_name,
                    number_of_images=series.number_of_images,
                    status=MassTransferVolume.Status.PENDING,
                )
            )

        return MassTransferVolume.objects.bulk_create(volumes)

    @staticmethod
    def _group_volumes(
        volumes: list[MassTransferVolume],
    ) -> dict[str, dict[str, list[MassTransferVolume]]]:
        """Group volumes by patient_id -> study_instance_uid."""
        grouped: dict[str, dict[str, list[MassTransferVolume]]] = {}
        for vol in volumes:
            grouped.setdefault(vol.patient_id, {}).setdefault(vol.study_instance_uid, []).append(
                vol
            )
        return grouped

    def _transfer_grouped_series(
        self,
        operator: DicomOperator,
        grouped_volumes: dict[str, dict[str, list[MassTransferVolume]]],
        job: MassTransferJob,
        pseudonymizer: Pseudonymizer | None,
        output_base: Path | None,
        dest_operator: DicomOperator | None = None,
    ) -> dict:
        """Transfer all grouped series.

        Iterates patients -> studies -> volumes, updating each volume in place.
        """
        total_processed = 0
        total_skipped = 0
        total_failed = 0
        total_volumes = 0
        study_count = 0
        failed_reasons: dict[str, int] = {}

        for patient_id, studies in grouped_volumes.items():
            for study_uid, volumes_list in studies.items():
                study_count += 1

                # One fetch association per study
                try:
                    for volume in volumes_list:
                        total_volumes += 1

                        if total_processed + total_failed + total_skipped > 0:
                            # Pacing delay between consecutive C-GET/C-MOVE requests.
                            # Some PACS servers reject or drop associations under
                            # rapid-fire requests. Batch transfer does not need this
                            # because it processes fewer series per task. The 0.5s
                            # value was chosen empirically.
                            # TODO: Investigate if this is really needed and if the
                            # delay value is appropriate (was never necessary in mass
                            # transfer which also transfers series one by one).
                            time.sleep(_DELAY_BETWEEN_SERIES)

                        subject_id = volume.pseudonym or sanitize_filename(volume.patient_id)
                        self._transfer_single_series(
                            operator,
                            volume,
                            job,
                            pseudonymizer,
                            subject_id,
                            output_base,
                            dest_operator,
                        )

                        if volume.status == MassTransferVolume.Status.ERROR:
                            total_failed += 1
                            reason = _short_error_reason(volume.log) if volume.log else "Unknown"
                            failed_reasons[reason] = failed_reasons.get(reason, 0) + 1
                        elif volume.status == MassTransferVolume.Status.SKIPPED:
                            total_skipped += 1
                        else:
                            total_processed += 1
                finally:
                    operator.close()

        return self._build_task_summary(
            total_volumes,
            study_count,
            total_processed,
            total_skipped,
            total_failed,
            failed_reasons,
        )

    def _transfer_single_series(
        self,
        operator: DicomOperator,
        volume: MassTransferVolume,
        job: MassTransferJob,
        pseudonymizer: Pseudonymizer | None,
        subject_id: str,
        output_base: Path | None,
        dest_operator: DicomOperator | None = None,
    ) -> None:
        """Export (and optionally convert) a single series.

        Updates volume fields in place and saves. Never raises except for
        RetriableDicomError.
        """
        try:
            if dest_operator:
                self._export_series_to_server(
                    operator,
                    volume,
                    pseudonymizer,
                    subject_id,
                    dest_operator,
                )
            else:
                assert output_base is not None
                study_folder = _study_folder_name(
                    volume.study_description,
                    volume.study_datetime,
                )
                series_folder = _series_folder_name(
                    volume.series_description,
                    volume.series_number,
                    volume.series_instance_uid,
                )
                output_path = (
                    output_base
                    / self.mass_task.partition_key
                    / subject_id
                    / study_folder
                    / series_folder
                )

                if job.convert_to_nifti:
                    self._export_and_convert_series(
                        operator,
                        volume,
                        pseudonymizer,
                        subject_id,
                        output_path,
                    )
                else:
                    self._export_series_to_folder(
                        operator,
                        volume,
                        pseudonymizer,
                        subject_id,
                        output_path,
                    )
        except RetriableDicomError:
            volume.status = MassTransferVolume.Status.ERROR
            volume.log = "Transfer interrupted by retriable error; task will be retried."
            raise
        except Exception as err:
            logger.exception(
                "Mass transfer failed for series %s",
                volume.series_instance_uid,
            )
            volume.status = MassTransferVolume.Status.ERROR
            volume.log = str(err)
        finally:
            if volume.status == MassTransferVolume.Status.PENDING:
                logger.error(
                    "Volume %s still PENDING after transfer — setting to ERROR.",
                    volume.series_instance_uid,
                )
                volume.status = MassTransferVolume.Status.ERROR
                volume.log = "Internal error: volume status was not updated after transfer."
            try:
                volume.save(
                    update_fields=[
                        "status",
                        "log",
                        "study_instance_uid_pseudonymized",
                        "series_instance_uid_pseudonymized",
                        "converted_file",
                        "updated",
                    ]
                )
            except Exception:
                logger.exception(
                    "Failed to save volume %s status to database",
                    volume.series_instance_uid,
                )

    def _export_and_convert_series(
        self,
        operator: DicomOperator,
        volume: MassTransferVolume,
        pseudonymizer: Pseudonymizer | None,
        subject_id: str,
        output_path: Path,
    ) -> None:
        """Export a series to a temp dir, then convert to NIfTI.

        Updates volume fields in place (status, pseudonymized UIDs, converted_file).
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            image_count, study_uid_pseudonymized, series_uid_pseudonymized = self._export_series(
                operator,
                volume,
                tmp_path,
                subject_id,
                pseudonymizer,
            )

            if image_count == 0:
                self._set_zero_image_status(
                    volume, study_uid_pseudonymized, series_uid_pseudonymized
                )
                return

            dicom_metadata = _extract_dicom_metadata(tmp_path)
            nifti_files = self._convert_series(volume, tmp_path, output_path)

            volume.study_instance_uid_pseudonymized = study_uid_pseudonymized
            volume.series_instance_uid_pseudonymized = series_uid_pseudonymized

            if nifti_files:
                _merge_dicom_metadata(output_path, dicom_metadata)
                volume.converted_file = "\n".join(str(f) for f in nifti_files)
                volume.status = MassTransferVolume.Status.CONVERTED
            else:
                volume.status = MassTransferVolume.Status.SKIPPED
                volume.log = "No valid DICOM images for NIfTI conversion"

    def _export_series_to_folder(
        self,
        operator: DicomOperator,
        volume: MassTransferVolume,
        pseudonymizer: Pseudonymizer | None,
        subject_id: str,
        output_path: Path,
    ) -> None:
        """Export a series directly to the output folder (no NIfTI conversion).

        Updates volume fields in place (status, pseudonymized UIDs).
        """
        image_count, study_uid_pseudonymized, series_uid_pseudonymized = self._export_series(
            operator,
            volume,
            output_path,
            subject_id,
            pseudonymizer,
        )

        if image_count == 0:
            self._set_zero_image_status(volume, study_uid_pseudonymized, series_uid_pseudonymized)
            return

        volume.study_instance_uid_pseudonymized = study_uid_pseudonymized
        volume.series_instance_uid_pseudonymized = series_uid_pseudonymized
        volume.status = MassTransferVolume.Status.EXPORTED

    def _export_series_to_server(
        self,
        operator: DicomOperator,
        volume: MassTransferVolume,
        pseudonymizer: Pseudonymizer | None,
        subject_id: str,
        dest_operator: DicomOperator,
    ) -> None:
        """Export a series to a temp dir and upload to a destination server.

        Updates volume fields in place (status, pseudonymized UIDs).
        """
        with tempfile.TemporaryDirectory(prefix="adit_") as tmpdir:
            tmp_path = Path(tmpdir)
            image_count, study_uid_pseudonymized, series_uid_pseudonymized = self._export_series(
                operator,
                volume,
                tmp_path,
                subject_id,
                pseudonymizer,
            )

            if image_count == 0:
                self._set_zero_image_status(
                    volume, study_uid_pseudonymized, series_uid_pseudonymized
                )
                return

            logger.debug(
                "Uploading %d images for series %s to destination server",
                image_count,
                volume.series_instance_uid,
            )
            dest_operator.upload_images(tmp_path)

        volume.study_instance_uid_pseudonymized = study_uid_pseudonymized
        volume.series_instance_uid_pseudonymized = series_uid_pseudonymized
        volume.status = MassTransferVolume.Status.EXPORTED

    @staticmethod
    def _set_zero_image_status(
        volume: MassTransferVolume,
        study_uid_pseudonymized: str,
        series_uid_pseudonymized: str,
    ) -> None:
        """Set status on a volume where the fetch returned 0 images."""
        volume.study_instance_uid_pseudonymized = study_uid_pseudonymized
        volume.series_instance_uid_pseudonymized = series_uid_pseudonymized
        if volume.number_of_images == 0:
            volume.status = MassTransferVolume.Status.SKIPPED
            volume.log = "Non-image series (0 instances in PACS)"
        else:
            volume.status = MassTransferVolume.Status.ERROR
            volume.log = (
                f"Fetch returned 0 images (PACS reports {volume.number_of_images} instances)"
            )

    def _build_task_summary(
        self,
        total_volumes: int,
        study_count: int,
        total_processed: int,
        total_skipped: int,
        total_failed: int,
        failed_reasons: dict[str, int],
    ) -> dict:
        """Build the final status dict returned to the task processor."""
        log_lines = [
            f"Partition {self.mass_task.partition_key}",
            f"Studies found: {study_count}",
            f"Series found: {total_volumes}",
            f"Processed: {total_processed}",
        ]
        if total_skipped:
            log_lines.append(f"Skipped: {total_skipped}")
        if total_failed:
            log_lines.append(f"Failed: {total_failed}")
        if failed_reasons:
            log_lines.append("Failure reasons:")
            for reason, count in failed_reasons.items():
                log_lines.append(f"  {count}x {reason}")

        if total_volumes == 0:
            status = MassTransferTask.Status.SUCCESS
            message = "No series found for this partition."
        elif total_failed and not total_processed:
            status = MassTransferTask.Status.FAILURE
            message = f"All {total_failed} series failed during mass transfer."
        else:
            total_series = total_processed + total_failed + total_skipped
            parts = [f"{total_processed} downloaded"]
            if total_failed:
                parts.append(f"{total_failed} failed")
            if total_skipped:
                parts.append(f"{total_skipped} skipped")

            status = (
                MassTransferTask.Status.WARNING if total_failed else MassTransferTask.Status.SUCCESS
            )
            message = f"{study_count} studies, {total_series} series ({', '.join(parts)})."

        return {
            "status": status,
            "message": message,
            "log": "\n".join(log_lines),
        }

    def _discover_series(
        self,
        operator: DicomOperator,
        filters: list[FilterSpec],
    ) -> list[DiscoveredSeries]:
        start = self.mass_task.partition_start
        end = self.mass_task.partition_end

        found: dict[str, DiscoveredSeries] = {}

        for mf in filters:
            studies = self._find_studies(operator, mf, start, end)

            for study in studies:
                if mf.modality and mf.modality not in study.ModalitiesInStudy:
                    continue

                if mf.study_description and not _dicom_match(
                    mf.study_description, study.StudyDescription
                ):
                    continue

                if mf.institution_name and mf.apply_institution_on_study:
                    if not self._study_has_institution(operator, study, mf.institution_name):
                        continue

                # Exact client-side age filtering using actual StudyDate and
                # PatientBirthDate (the query birth date range is approximate).
                birth_date = study.PatientBirthDate
                has_age_filter = mf.min_age is not None or mf.max_age is not None
                if birth_date and study.StudyDate and has_age_filter:
                    age = _age_at_study(birth_date, study.StudyDate)
                    if mf.min_age is not None and age < mf.min_age:
                        continue
                    if mf.max_age is not None and age > mf.max_age:
                        continue

                series_query = QueryDataset.create(
                    PatientID=study.PatientID,
                    StudyInstanceUID=study.StudyInstanceUID,
                )
                series_query.dataset.InstitutionName = ""

                series_list = list(operator.find_series(series_query))

                for series in series_list:
                    series_uid = series.SeriesInstanceUID
                    if not series_uid:
                        continue

                    series_number = _parse_int(series.get("SeriesNumber"), default=None)

                    if (
                        mf.institution_name
                        and not mf.apply_institution_on_study
                        and not _dicom_match(
                            mf.institution_name, series.get("InstitutionName", None)
                        )
                    ):
                        continue

                    if mf.modality and mf.modality != series.Modality:
                        continue

                    if mf.series_description and not _dicom_match(
                        mf.series_description, series.SeriesDescription
                    ):
                        continue

                    if mf.series_number is not None:
                        try:
                            if series_number is None or mf.series_number != series_number:
                                continue
                        except (TypeError, ValueError):
                            continue

                    if mf.min_number_of_series_related_instances is not None:
                        num_instances = (
                            _parse_int(series.get("NumberOfSeriesRelatedInstances"), default=0) or 0
                        )
                        if num_instances < mf.min_number_of_series_related_instances:
                            continue

                    if series_uid in found:
                        continue

                    study_dt = _study_datetime(study)
                    found[series_uid] = DiscoveredSeries(
                        patient_id=str(study.PatientID),
                        accession_number=str(study.get("AccessionNumber", "")),
                        study_instance_uid=str(study.StudyInstanceUID),
                        series_instance_uid=str(series_uid),
                        modality=str(series.Modality),
                        study_description=str(study.get("StudyDescription", "")),
                        series_description=str(series.get("SeriesDescription", "")),
                        series_number=series_number,
                        study_datetime=study_dt,
                        institution_name=str(series.get("InstitutionName", "")),
                        number_of_images=_parse_int(
                            series.get("NumberOfSeriesRelatedInstances"), default=0
                        )
                        or 0,
                        patient_birth_date=birth_date,
                    )

        return list(found.values())

    def _find_studies(
        self,
        operator: DicomOperator,
        mf: FilterSpec,
        start: datetime,
        end: datetime,
    ) -> list[ResultDataset]:
        max_results = operator.server.max_search_results

        # DICOM applies StudyTime independently per day, so a cross-midnight
        # range like Date=20250227-20250228 Time=234500-000730 does NOT mean
        # "from Feb 27 23:45 to Feb 28 00:07".  When the window is within a
        # single day we can use precise time filtering.  For multi-day ranges
        # we use full-day times and rely on date-based splitting.  But when
        # the window has narrowed to just two consecutive days (i.e. a
        # cross-midnight split), we split at midnight so each half becomes a
        # single-day query with proper time filtering.
        if start.date() != end.date():
            days_apart = (end.date() - start.date()).days
            if days_apart <= 1:
                # Cross-midnight: split at midnight boundary
                midnight = datetime.combine(end.date(), datetime.min.time(), tzinfo=end.tzinfo)
                left = self._find_studies(operator, mf, start, midnight - timedelta(seconds=1))
                right = self._find_studies(operator, mf, midnight, end)

                seen: set[str] = {str(s.StudyInstanceUID) for s in left}
                for study in right:
                    if str(study.StudyInstanceUID) not in seen:
                        left.append(study)
                        seen.add(str(study.StudyInstanceUID))

                return left

            # Multi-day: full-day times, splitting will narrow by date
            study_time = (datetime.min.time(), datetime.max.time().replace(microsecond=0))
        else:
            study_time = (start.time(), end.time())

        birth_range = _birth_date_range(
            start.date(),
            end.date(),
            mf.min_age,
            mf.max_age,
        )
        birth_date_kwarg: dict[str, tuple[date, date]] = {}
        if birth_range:
            birth_date_kwarg["PatientBirthDate"] = birth_range
        query = QueryDataset.create(
            StudyDate=(start.date(), end.date()),
            StudyTime=study_time,
            **birth_date_kwarg,  # type: ignore[arg-type]
        )

        if mf.modality:
            query.dataset.ModalitiesInStudy = mf.modality
        if mf.study_description:
            query.dataset.StudyDescription = mf.study_description

        studies = list(operator.find_studies(query, limit_results=max_results + 1))

        if len(studies) > max_results:
            if end - start < _MIN_SPLIT_WINDOW:
                raise DicomError(f"Time window too small ({start} to {end}) for filter {mf}.")

            mid = start + (end - start) / 2
            left = self._find_studies(operator, mf, start, mid)
            right = self._find_studies(operator, mf, mid + timedelta(seconds=1), end)

            seen: set[str] = {str(s.StudyInstanceUID) for s in left}
            for study in right:
                if str(study.StudyInstanceUID) not in seen:
                    left.append(study)
                    seen.add(str(study.StudyInstanceUID))

            return left

        return studies

    def _study_has_institution(
        self,
        operator: DicomOperator,
        study: ResultDataset,
        institution_name: str,
    ) -> bool:
        series_query = QueryDataset.create(
            PatientID=study.PatientID,
            StudyInstanceUID=study.StudyInstanceUID,
        )
        series_query.dataset.InstitutionName = ""

        series_list = list(operator.find_series(series_query))
        return any(
            _dicom_match(institution_name, series.get("InstitutionName", None))
            for series in series_list
        )

    def _export_series(
        self,
        operator: DicomOperator,
        volume: MassTransferVolume,
        output_path: Path,
        subject_id: str,
        pseudonymizer: Pseudonymizer | None,
    ) -> tuple[int, str, str]:
        """Export a series to output_path.

        Returns (image_count, pseudonymized_study_uid, pseudonymized_series_uid).
        """
        output_path.mkdir(parents=True, exist_ok=True)

        manipulator = DicomManipulator(pseudonymizer=pseudonymizer) if pseudonymizer else None
        image_count = 0
        study_uid_pseudonymized = ""
        series_uid_pseudonymized = ""

        def callback(ds: Dataset | None) -> None:
            nonlocal image_count, study_uid_pseudonymized, series_uid_pseudonymized
            if ds is None:
                return
            if manipulator:
                job = self.mass_task.job
                manipulator.manipulate(
                    ds,
                    pseudonym=subject_id,
                    trial_protocol_id=job.trial_protocol_id,
                    trial_protocol_name=job.trial_protocol_name,
                )
                if not study_uid_pseudonymized:
                    study_uid_pseudonymized = str(ds.StudyInstanceUID)
                    series_uid_pseudonymized = str(ds.SeriesInstanceUID)
            file_name = sanitize_filename(f"{ds.SOPInstanceUID}.dcm")
            write_dataset(ds, output_path / file_name)
            image_count += 1

        # Reconciliation between the discovery and transfer phases: discovery
        # recorded volume.number_of_images from the PACS's own C-FIND response;
        # a fetch that delivers 0 images against a non-zero expected count means
        # the PACS either got momentarily overloaded or the series sits on
        # archived/offline storage. We probe once more to distinguish the two.
        # This is workflow logic, not network retry — transient connection
        # failures are still handled by stamina/procrastinate at lower layers.
        operator.fetch_series(
            patient_id=volume.patient_id,
            study_uid=volume.study_instance_uid,
            series_uid=volume.series_instance_uid,
            callback=callback,
        )
        if image_count == 0 and volume.number_of_images > 0:
            logger.warning(
                "Fetch returned 0 images for %s (PACS reports %d) — retrying in %ds",
                volume.series_instance_uid,
                volume.number_of_images,
                settings.MASS_TRANSFER_FETCH_RECONCILIATION_DELAY,
            )
            time.sleep(settings.MASS_TRANSFER_FETCH_RECONCILIATION_DELAY)
            operator.fetch_series(
                patient_id=volume.patient_id,
                study_uid=volume.study_instance_uid,
                series_uid=volume.series_instance_uid,
                callback=callback,
            )

        if image_count == 0 and volume.number_of_images > 0:
            logger.error(
                "Fetch returned 0 images for %s (PACS reports %d) — may be archived/offline",
                volume.series_instance_uid,
                volume.number_of_images,
            )

        if image_count == 0:
            try:
                if output_path.exists() and not any(output_path.iterdir()):
                    output_path.rmdir()
            except OSError:
                logger.debug("Failed to remove empty directory %s", output_path, exc_info=True)

        return image_count, study_uid_pseudonymized, series_uid_pseudonymized

    def _convert_series(
        self,
        volume: MassTransferVolume,
        dicom_dir: Path,
        output_path: Path,
    ) -> list[Path]:
        """Convert DICOM to NIfTI. Returns list of produced .nii.gz files (empty for non-image)."""
        from adit.core.utils.dicom_to_nifti_converter import DicomToNiftiConverter

        output_path.mkdir(parents=True, exist_ok=True)

        converter = DicomToNiftiConverter()
        try:
            converter.convert(dicom_dir, output_path)
        except RuntimeError as exc:
            err_msg = str(exc)
            if "No valid DICOM" in err_msg:
                try:
                    if output_path.exists() and not any(output_path.iterdir()):
                        output_path.rmdir()
                except OSError:
                    logger.debug("Failed to remove empty directory %s", output_path, exc_info=True)
                return []
            raise DicomError(
                f"Conversion failed for series {volume.series_instance_uid}: {err_msg}"
            )

        nifti_files = sorted(output_path.glob("*.nii.gz"))
        if not nifti_files:
            raise DicomError(
                f"dcm2niix produced no .nii.gz files for series {volume.series_instance_uid}"
            )
        return nifti_files
