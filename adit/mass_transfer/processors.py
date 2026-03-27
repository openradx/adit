from __future__ import annotations

import hashlib
import json
import logging
import random
import secrets
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import cast

from django.utils import timezone
from pydicom import Dataset

from adit.core.errors import DicomError, RetriableDicomError
from adit.core.models import DicomNode, DicomTask
from adit.core.processors import DicomTaskProcessor
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import convert_to_python_regex, write_dataset
from adit.core.utils.pseudonymizer import Pseudonymizer
from adit.core.utils.sanitize import sanitize_filename

from .models import (
    MassTransferJob,
    MassTransferSettings,
    MassTransferTask,
    MassTransferVolume,
)


@dataclass
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
        )

logger = logging.getLogger(__name__)

_MIN_SPLIT_WINDOW = timedelta(minutes=30)


@dataclass
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


def _study_folder_name(study_description: str, study_dt: datetime, study_uid: str) -> str:
    desc = sanitize_filename(study_description or "Undefined")
    dt_str = study_dt.strftime("%Y%m%d_%H%M%S")
    short_hash = hashlib.sha256(study_uid.encode()).hexdigest()[:4]
    return f"{desc}_{dt_str}_{short_hash}"


def _series_folder_name(series_description: str, series_number: int | None, series_uid: str) -> str:
    if series_number is None:
        return sanitize_filename(series_uid)
    desc = sanitize_filename(series_description or "Undefined")
    return f"{desc}_{series_number}"


_SIDECAR_DICOM_TAGS = [
    "PatientBirthDate",
    "PatientSex",
    "PatientAge",
    "PatientID",
    "PatientName",
    "StudyDate",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "Modality",
    "InstitutionName",
    "StudyDescription",
    "SeriesDescription",
    "SeriesNumber",
]


def _extract_dicom_sidecar(dicom_dir: Path) -> dict[str, str]:
    """Read the first DICOM file in *dicom_dir* and extract sidecar fields.

    These are post-pseudonymization values — shifted dates, replaced UIDs,
    etc. The function also computes a ``PatientAgeAtStudy`` field from
    PatientBirthDate and StudyDate when both are present.
    """
    import pydicom

    for dcm_path in sorted(dicom_dir.glob("*.dcm")):
        try:
            ds = pydicom.dcmread(dcm_path, stop_before_pixels=True)
        except Exception:
            continue
        fields: dict[str, str] = {}
        for tag in _SIDECAR_DICOM_TAGS:
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


def _write_dicom_sidecar(output_path: Path, sidecar_name: str, fields: dict[str, str]) -> None:
    """Write a DICOM metadata sidecar JSON file alongside NIfTI outputs."""
    if not fields:
        return
    sidecar_path = output_path / f"{sidecar_name}_dicom.json"
    try:
        sidecar_path.write_text(json.dumps(fields, indent=2))
    except Exception:
        logger.warning("Failed to write sidecar %s", sidecar_path, exc_info=True)


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
    """Compute a PatientBirthDate range for C-FIND from age bounds.

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
        if destination_node.node_type != DicomNode.NodeType.FOLDER:
            raise DicomError("Mass transfer destination must be a DICOM folder.")

        filters = job.get_filters()

        if not filters:
            return {
                "status": MassTransferTask.Status.FAILURE,
                "message": "No filters configured for this job.",
                "log": "Mass transfer requires at least one filter.",
            }

        pseudonymizer: Pseudonymizer | None = None
        if job.pseudonymize and job.pseudonym_salt:
            pseudonymizer = Pseudonymizer(seed=job.pseudonym_salt)
        elif job.pseudonymize:
            pseudonymizer = Pseudonymizer()

        output_base = _destination_base_dir(destination_node, job)

        # Clean up partition on retry: delete the partition folder on disk
        # and all existing volumes for this partition in the DB.
        partition_path = output_base / self.mass_task.partition_key
        if partition_path.exists():
            shutil.rmtree(partition_path)
        MassTransferVolume.objects.filter(
            job=job,
            partition_key=self.mass_task.partition_key,
        ).delete()

        operator = DicomOperator(source_node.dicomserver)
        operator.dimse_connector.auto_close = False

        # Discovery: one C-FIND association for all queries
        discovered = self._discover_series(operator, filters)
        operator.close()

        grouped, subject_ids = self._group_series(discovered, job, pseudonymizer)

        # Transfer: one C-GET association per study
        return self._transfer_grouped_series(
            operator, grouped, subject_ids, job, pseudonymizer, output_base, discovered,
        )

    def _group_series(
        self,
        discovered: list[DiscoveredSeries],
        job: MassTransferJob,
        pseudonymizer: Pseudonymizer | None,
    ) -> tuple[
        dict[str, dict[str, list[DiscoveredSeries]]],
        dict[str, str],
    ]:
        """Group discovered series by patient -> study.

        Returns:
            grouped: {patient_id: {study_uid: [series, ...]}}
            subject_ids: {patient_id: subject_id} mapping for folder names.
                For deterministic (linked) mode, maps patient_id -> pseudonym.
                For no-anonymization mode, maps patient_id -> sanitized patient_id.
                For random mode, subject_ids is empty here — random pseudonyms
                are assigned per-study in _transfer_grouped_series.
        """
        subject_ids: dict[str, str] = {}
        grouped: dict[str, dict[str, list[DiscoveredSeries]]] = {}

        for series in discovered:
            pid = series.patient_id
            study_uid = series.study_instance_uid

            if pid not in subject_ids:
                if pseudonymizer and job.pseudonym_salt:
                    # Deterministic (linked): same patient always gets same pseudonym
                    subject_ids[pid] = pseudonymizer.compute_pseudonym(pid)
                elif not pseudonymizer:
                    # No anonymization: use raw patient ID as folder name
                    subject_ids[pid] = sanitize_filename(pid)
                # else: random mode — subject_id assigned per-study during transfer

            grouped.setdefault(pid, {}).setdefault(study_uid, []).append(series)

        return grouped, subject_ids

    def _transfer_grouped_series(
        self,
        operator: DicomOperator,
        grouped: dict[str, dict[str, list[DiscoveredSeries]]],
        subject_ids: dict[str, str],
        job: MassTransferJob,
        pseudonymizer: Pseudonymizer | None,
        output_base: Path,
        discovered: list[DiscoveredSeries],
    ) -> dict:
        """Transfer all grouped series via C-GET.

        Iterates patients -> studies -> series.
        """
        done_status = (
            MassTransferVolume.Status.CONVERTED
            if job.convert_to_nifti
            else MassTransferVolume.Status.EXPORTED
        )

        total_processed = 0
        total_skipped = 0
        total_failed = 0
        failed_reasons: dict[str, int] = {}
        random_pseudonyms: dict[str, str] = {}

        for patient_id, studies in grouped.items():
            subject_id = subject_ids.get(patient_id, "")

            for study_uid, series_list in studies.items():
                # For random pseudonymization, use per-study pseudonym
                if pseudonymizer and not job.pseudonym_salt:
                    if study_uid not in random_pseudonyms:
                        random_pseudonyms[study_uid] = secrets.token_hex(6).upper()
                    subject_id = random_pseudonyms[study_uid]

                # One C-GET association per study
                try:
                    for series in series_list:
                        study_folder = _study_folder_name(
                            series.study_description,
                            series.study_datetime,
                            series.study_instance_uid,
                        )
                        series_folder = _series_folder_name(
                            series.series_description,
                            series.series_number,
                            series.series_instance_uid,
                        )

                        try:
                            # Small delay between C-GET requests to avoid
                            # overwhelming the PACS.
                            if total_processed + total_failed + total_skipped > 0:
                                time.sleep(0.5)

                            if job.convert_to_nifti:
                                with tempfile.TemporaryDirectory() as tmp_dir:
                                    tmp_path = Path(tmp_dir)
                                    image_count, p_study_uid, p_series_uid = (
                                        self._export_series(
                                            operator,
                                            series,
                                            tmp_path,
                                            subject_id,
                                            pseudonymizer,
                                        )
                                    )
                                    if image_count == 0:
                                        nifti_files = []
                                    else:
                                        dicom_sidecar = _extract_dicom_sidecar(tmp_path)
                                        output_path = (
                                            output_base
                                            / self.mass_task.partition_key
                                            / subject_id
                                            / study_folder
                                            / series_folder
                                        )
                                        nifti_files = self._convert_series(
                                            series,
                                            tmp_path,
                                            output_path,
                                        )
                                        if nifti_files:
                                            _write_dicom_sidecar(
                                                output_path,
                                                series_folder,
                                                dicom_sidecar,
                                            )
                            else:
                                output_path = (
                                    output_base
                                    / self.mass_task.partition_key
                                    / subject_id
                                    / study_folder
                                    / series_folder
                                )
                                image_count, p_study_uid, p_series_uid = self._export_series(
                                    operator,
                                    series,
                                    output_path,
                                    subject_id,
                                    pseudonymizer,
                                )
                                nifti_files = []

                            converted_file = ""
                            if image_count == 0:
                                if series.number_of_images == 0:
                                    status = MassTransferVolume.Status.SKIPPED
                                    log_msg = "Non-image series (0 instances in PACS)"
                                else:
                                    status = MassTransferVolume.Status.ERROR
                                    log_msg = (
                                        f"C-GET returned 0 images"
                                        f" (PACS reports {series.number_of_images}"
                                        f" instances)"
                                    )
                            elif nifti_files:
                                converted_file = "\n".join(str(f) for f in nifti_files)
                                status = done_status
                                log_msg = ""
                            elif job.convert_to_nifti:
                                status = MassTransferVolume.Status.SKIPPED
                                log_msg = "No valid DICOM images for NIfTI conversion"
                            else:
                                status = done_status
                                log_msg = ""

                            MassTransferVolume.objects.create(
                                job=job,
                                task=self.mass_task,
                                partition_key=self.mass_task.partition_key,
                                patient_id=series.patient_id,
                                pseudonym=subject_id if pseudonymizer else "",
                                accession_number=series.accession_number,
                                study_instance_uid=series.study_instance_uid,
                                study_instance_uid_pseudonymized=p_study_uid,
                                series_instance_uid=series.series_instance_uid,
                                series_instance_uid_pseudonymized=p_series_uid,
                                modality=series.modality,
                                study_description=series.study_description,
                                series_description=series.series_description,
                                series_number=series.series_number,
                                study_datetime=timezone.make_aware(series.study_datetime),
                                institution_name=series.institution_name,
                                number_of_images=series.number_of_images,
                                converted_file=converted_file,
                                status=status,
                                log=log_msg,
                            )

                            if status == MassTransferVolume.Status.ERROR:
                                total_failed += 1
                                reason = "C-GET returned 0 images"
                                failed_reasons[reason] = failed_reasons.get(reason, 0) + 1
                            elif status == MassTransferVolume.Status.SKIPPED:
                                total_skipped += 1
                            else:
                                total_processed += 1

                        except RetriableDicomError:
                            raise
                        except Exception as err:
                            logger.exception(
                                "Mass transfer failed for series %s",
                                series.series_instance_uid,
                            )
                            MassTransferVolume.objects.create(
                                job=job,
                                task=self.mass_task,
                                partition_key=self.mass_task.partition_key,
                                patient_id=series.patient_id,
                                pseudonym=subject_id if pseudonymizer else "",
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
                                status=MassTransferVolume.Status.ERROR,
                                log=str(err),
                            )
                            total_failed += 1
                            reason = _short_error_reason(str(err))
                            failed_reasons[reason] = failed_reasons.get(reason, 0) + 1
                finally:
                    operator.close()

        # Count unique studies across all discovered series
        study_uids = {s.study_instance_uid for s in discovered}

        log_lines = [
            f"Partition {self.mass_task.partition_key}",
            f"Studies found: {len(study_uids)}",
            f"Series found: {len(discovered)}",
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

        if not discovered:
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
                MassTransferTask.Status.WARNING
                if total_failed
                else MassTransferTask.Status.SUCCESS
            )
            message = (
                f"{len(study_uids)} studies, {total_series} series ({', '.join(parts)})."
            )

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
                # PatientBirthDate (the C-FIND birth date range is approximate).
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
                        ) or 0,
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
            start.date(), end.date(), mf.min_age, mf.max_age,
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

        for series in operator.find_series(series_query):
            institution = series.get("InstitutionName", None)
            if _dicom_match(institution_name, institution):
                return True

        return False

    def _export_series(
        self,
        operator: DicomOperator,
        series: DiscoveredSeries,
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
        pseudo_study_uid = ""
        pseudo_series_uid = ""

        def callback(ds: Dataset | None) -> None:
            nonlocal image_count, pseudo_study_uid, pseudo_series_uid
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
                if not pseudo_study_uid:
                    pseudo_study_uid = str(ds.StudyInstanceUID)
                    pseudo_series_uid = str(ds.SeriesInstanceUID)
            file_name = sanitize_filename(f"{ds.SOPInstanceUID}.dcm")
            write_dataset(ds, output_path / file_name)
            image_count += 1

        # IMPAX returns "Success with 0 sub-operations" for two reasons:
        # 1. Transient: PACS is overwhelmed by rapid requests (fixed by pacing)
        # 2. Permanent: series is archived/offline and can't be served via C-GET
        # One retry after a short delay distinguishes the two cases.  If the
        # second attempt also fails, the series is unretrievable — move on and
        # let the ERROR status trigger a retry on the next task run.
        operator.fetch_series(
            patient_id=series.patient_id,
            study_uid=series.study_instance_uid,
            series_uid=series.series_instance_uid,
            callback=callback,
        )
        if image_count == 0 and series.number_of_images > 0:
            delay = 3 + random.random() * 2
            logger.warning(
                "C-GET returned 0 images for %s (PACS reports %d) — retrying in %.0fs",
                series.series_instance_uid,
                series.number_of_images,
                delay,
            )
            time.sleep(delay)
            operator.fetch_series(
                patient_id=series.patient_id,
                study_uid=series.study_instance_uid,
                series_uid=series.series_instance_uid,
                callback=callback,
            )

        if image_count == 0 and series.number_of_images > 0:
            logger.error(
                "C-GET returned 0 images for %s (PACS reports %d) — series may be archived/offline",
                series.series_instance_uid,
                series.number_of_images,
            )

        if image_count == 0:
            try:
                if output_path.exists() and not any(output_path.iterdir()):
                    output_path.rmdir()
            except OSError:
                pass

        return image_count, pseudo_study_uid, pseudo_series_uid

    def _convert_series(
        self,
        series: DiscoveredSeries,
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
                    pass
                return []
            raise DicomError(
                f"Conversion failed for series {series.series_instance_uid}: {err_msg}"
            )

        nifti_files = sorted(output_path.glob("*.nii.gz"))
        if not nifti_files:
            raise DicomError(
                f"dcm2niix produced no .nii.gz files for series {series.series_instance_uid}"
            )
        return nifti_files
