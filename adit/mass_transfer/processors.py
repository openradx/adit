from __future__ import annotations

import logging
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from django.conf import settings
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
    MassTransferFilter,
    MassTransferSettings,
    MassTransferTask,
    MassTransferVolume,
)

logger = logging.getLogger(__name__)

_MIN_SPLIT_WINDOW = timedelta(minutes=30)


def _dicom_match(pattern: str, value: str | None) -> bool:
    if not pattern:
        return True
    if value is None:
        return False
    regex = convert_to_python_regex(pattern)
    return bool(regex.search(str(value)))


def _short_error_reason(error: str) -> str:
    """Extract a short, groupable reason from a volume error message."""
    # Take the last non-empty line — for dcm2niix output this is the
    # meaningful summary (e.g. "No valid DICOM images were found").
    lines = [line.strip() for line in error.strip().splitlines() if line.strip()]
    return lines[-1] if lines else error


def _parse_int(value: object, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(cast(str, value))
    except (TypeError, ValueError):
        return default


def _series_folder_name(
    series_number: int | None, series_description: str, series_uid: str
) -> str:
    if series_number is None:
        base = series_uid
    else:
        description = series_description or "Undefined"
        base = f"{series_number}-{description}"
    return sanitize_filename(str(base))


def _study_datetime(study: ResultDataset) -> datetime:
    study_date = study.StudyDate
    study_time = study.StudyTime
    if study_time is None:
        study_time = datetime.min.time()
    return datetime.combine(study_date, study_time)


def _export_base_dir() -> Path:
    base = Path(settings.MASS_TRANSFER_EXPORT_BASE_DIR)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _destination_base_dir(node: DicomNode) -> Path:
    assert node.node_type == DicomNode.NodeType.FOLDER
    path = Path(node.dicomfolder.path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _volume_path(
    base_dir: Path,
    study_dt: datetime,
    subject_id: str,
    series_name: str,
) -> Path:
    year_month = study_dt.strftime("%Y%m")
    return base_dir / year_month / subject_id / series_name


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
        source_node = job.source
        destination_node = job.destination

        if source_node.node_type != DicomNode.NodeType.SERVER:
            raise DicomError("Mass transfer source must be a DICOM server.")
        if destination_node.node_type != DicomNode.NodeType.FOLDER:
            raise DicomError("Mass transfer destination must be a DICOM folder.")

        filters = list(job.filters.all())
        if not filters:
            return {
                "status": MassTransferTask.Status.FAILURE,
                "message": "No filters configured for this job.",
                "log": "Mass transfer requires at least one filter.",
            }

        # Discovery: query PACS and create volume records.
        # persistent=True keeps the DIMSE association open across multiple
        # C-FIND/C-GET calls instead of reconnecting for every operation.
        operator = DicomOperator(source_node.dicomserver, persistent=True)
        try:
            volumes = self._find_volumes(operator, filters)

            # Link all discovered volumes to this task (for cleanup_on_failure)
            for volume in volumes:
                if volume.task_id != self.mass_task.pk:
                    volume.task = self.mass_task
                    volume.save(update_fields=["task"])

            # Group volumes by study for pseudonymization — all series in a study
            # must share the same pseudonym so the data stays linked.
            volumes_by_study: dict[str, list[MassTransferVolume]] = {}
            for volume in volumes:
                volumes_by_study.setdefault(volume.study_instance_uid, []).append(volume)

            export_base = _export_base_dir()
            output_base = _destination_base_dir(destination_node)

            # The "done" status depends on whether NIfTI conversion is enabled:
            # CONVERTED when converting, EXPORTED when exporting DICOM only.
            done_status = (
                MassTransferVolume.Status.CONVERTED
                if job.convert_to_nifti
                else MassTransferVolume.Status.EXPORTED
            )

            total_processed = 0
            total_skipped = 0
            total_failed = 0
            failed_reasons: dict[str, int] = {}

            for study_uid, study_volumes in volumes_by_study.items():
                pseudonym = ""
                study_pseudonymizer: Pseudonymizer | None = None

                if job.should_pseudonymize:
                    existing_pseudonym = next(
                        (v.pseudonym for v in study_volumes if v.pseudonym),
                        None,
                    )
                    pseudonym = existing_pseudonym or uuid.uuid4().hex
                    # One Anonymizer per study: all series in the same study share
                    # the same Anonymizer so UIDs stay consistent within the study.
                    study_pseudonymizer = Pseudonymizer()

                for volume in study_volumes:
                    if volume.status == done_status:
                        total_processed += 1
                        continue
                    if volume.status == MassTransferVolume.Status.SKIPPED:
                        total_skipped += 1
                        continue

                    try:
                        if job.convert_to_nifti:
                            self._export_volume(
                                operator, volume, export_base, pseudonym,
                                study_pseudonymizer=study_pseudonymizer,
                            )
                            self._convert_volume(volume, output_base, pseudonym)
                        else:
                            self._export_volume(
                                operator, volume, output_base, pseudonym,
                                study_pseudonymizer=study_pseudonymizer,
                            )

                        # _convert_volume may set SKIPPED for non-image DICOMs
                        if volume.status == MassTransferVolume.Status.SKIPPED:
                            total_skipped += 1
                        else:
                            total_processed += 1
                    except RetriableDicomError:
                        raise  # let Procrastinate retry the entire task
                    except Exception as err:
                        logger.exception(
                            "Mass transfer failed for volume %s", volume.series_instance_uid
                        )
                        self._cleanup_export(volume)
                        volume.status = MassTransferVolume.Status.ERROR
                        volume.add_log(str(err))
                        volume.save()
                        total_failed += 1
                        reason = _short_error_reason(str(err))
                        failed_reasons[reason] = failed_reasons.get(reason, 0) + 1
        finally:
            operator.close()

        log_lines = [
            f"Partition {self.mass_task.partition_key}",
            f"Studies found: {len(volumes_by_study)}",
            f"Volumes found: {len(volumes)}",
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

        if not volumes:
            status = MassTransferTask.Status.SUCCESS
            message = "No volumes found for this partition."
        elif total_failed and not total_processed:
            status = MassTransferTask.Status.FAILURE
            message = f"All {total_failed} volumes failed during mass transfer."
        else:
            # Build a unified message: "x studies, y volumes processed (z skipped, w failed)"
            parts = []
            if total_skipped:
                parts.append(f"{total_skipped} skipped")
            if total_failed:
                parts.append(f"{total_failed} failed")
            suffix = f" ({', '.join(parts)})" if parts else ""

            if total_failed:
                status = MassTransferTask.Status.WARNING
            else:
                status = MassTransferTask.Status.SUCCESS

            message = (
                f"{len(volumes_by_study)} studies, "
                f"{total_processed} volumes processed{suffix}."
            )

        return {
            "status": status,
            "message": message,
            "log": "\n".join(log_lines),
        }

    def _find_volumes(
        self,
        operator: DicomOperator,
        filters: list[MassTransferFilter],
    ) -> list[MassTransferVolume]:
        start = self.mass_task.partition_start
        end = self.mass_task.partition_end
        job = self.mass_task.job

        found_series: dict[str, MassTransferVolume] = {}

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

                series_query = QueryDataset.create(
                    PatientID=study.PatientID,
                    StudyInstanceUID=study.StudyInstanceUID,
                )
                # Request institution name at series level when possible
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

                    if series_uid in found_series:
                        continue

                    study_dt = _study_datetime(study)
                    # Use get_or_create for resumability: if a task failed halfway
                    # and is retried, volumes that were already exported/converted
                    # are returned as-is and skipped later in the processing loop.
                    volume, created = MassTransferVolume.objects.get_or_create(
                        job=job,
                        series_instance_uid=series_uid,
                        defaults={
                            "partition_key": self.mass_task.partition_key,
                            "patient_id": str(study.PatientID),
                            "accession_number": str(study.get("AccessionNumber", "")),
                            "study_instance_uid": str(study.StudyInstanceUID),
                            "modality": str(series.Modality),
                            "study_description": str(study.get("StudyDescription", "")),
                            "series_description": str(series.get("SeriesDescription", "")),
                            "series_number": series_number,
                            "study_datetime": timezone.make_aware(study_dt),
                            "institution_name": str(series.get("InstitutionName", "")),
                            "number_of_images": _parse_int(
                                series.get("NumberOfSeriesRelatedInstances"), default=0
                            ),
                        },
                    )
                    # Refresh metadata from PACS in case it changed between runs,
                    # but only for volumes that haven't been processed yet to avoid
                    # clobbering partition_key on already exported/converted volumes.
                    if not created and volume.status == MassTransferVolume.Status.PENDING:
                        volume.partition_key = self.mass_task.partition_key
                        volume.patient_id = str(study.PatientID)
                        volume.accession_number = str(study.get("AccessionNumber", ""))
                        volume.study_instance_uid = str(study.StudyInstanceUID)
                        volume.modality = str(series.Modality)
                        volume.study_description = str(study.get("StudyDescription", ""))
                        volume.series_description = str(series.get("SeriesDescription", ""))
                        volume.series_number = series_number
                        volume.study_datetime = timezone.make_aware(study_dt)
                        volume.institution_name = str(series.get("InstitutionName", ""))
                        volume.number_of_images = _parse_int(
                            series.get("NumberOfSeriesRelatedInstances"), default=0
                        )
                        volume.save()

                    found_series[series_uid] = volume

        return list(found_series.values())

    def _find_studies(
        self,
        operator: DicomOperator,
        mf: MassTransferFilter,
        start: datetime,
        end: datetime,
    ) -> list[ResultDataset]:
        max_results = settings.MASS_TRANSFER_MAX_SEARCH_RESULTS

        query = QueryDataset.create(
            StudyDate=(start.date(), end.date()),
            StudyTime=(datetime.min.time(), datetime.max.time().replace(microsecond=0)),
        )

        if mf.modality:
            query.dataset.ModalitiesInStudy = mf.modality
        if mf.study_description:
            query.dataset.StudyDescription = mf.study_description

        studies = list(operator.find_studies(query, limit_results=max_results + 1))

        if len(studies) > max_results:
            if end - start < _MIN_SPLIT_WINDOW:
                raise DicomError(
                    f"Time window too small ({start} to {end}) for filter {mf}."
                )

            mid = start + (end - start) / 2
            left = self._find_studies(operator, mf, start, mid)
            right = self._find_studies(operator, mf, mid + timedelta(seconds=1), end)

            # Deduplicate: the date-level DICOM query can return the same study
            # in both halves when the split falls within a single day.
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

    def _export_volume(
        self,
        operator: DicomOperator,
        volume: MassTransferVolume,
        export_base: Path,
        pseudonym: str,
        *,
        study_pseudonymizer: Pseudonymizer | None = None,
    ) -> None:
        if volume.status == MassTransferVolume.Status.EXPORTED and volume.exported_folder:
            return

        study_dt = volume.study_datetime
        series_name = _series_folder_name(
            volume.series_number,
            volume.series_description,
            volume.series_instance_uid,
        )

        subject_id = sanitize_filename(pseudonym or volume.patient_id)
        export_path = _volume_path(export_base, study_dt, subject_id, series_name)
        export_path.mkdir(parents=True, exist_ok=True)
        volume.exported_folder = str(export_path)

        # Share the study-level Pseudonymizer (and thus Anonymizer) across
        # all volumes in the same study.
        manipulator = DicomManipulator(pseudonymizer=study_pseudonymizer)

        # Capture pseudonymized UIDs from the first image after anonymization.
        pseudonymized_study_uid = ""
        pseudonymized_series_uid = ""

        def callback(ds: Dataset | None) -> None:
            nonlocal pseudonymized_study_uid, pseudonymized_series_uid
            if ds is None:
                return
            manipulator.manipulate(ds, pseudonym=pseudonym)
            if pseudonym and not pseudonymized_study_uid:
                pseudonymized_study_uid = str(ds.StudyInstanceUID)
                pseudonymized_series_uid = str(ds.SeriesInstanceUID)
            file_name = sanitize_filename(f"{ds.SOPInstanceUID}.dcm")
            write_dataset(ds, export_path / file_name)

        operator.fetch_series(
            patient_id=volume.patient_id,
            study_uid=volume.study_instance_uid,
            series_uid=volume.series_instance_uid,
            callback=callback,
        )

        volume.pseudonym = pseudonym
        volume.study_instance_uid_pseudonymized = pseudonymized_study_uid
        volume.series_instance_uid_pseudonymized = pseudonymized_series_uid
        volume.status = MassTransferVolume.Status.EXPORTED
        volume.save()

    def _convert_volume(
        self,
        volume: MassTransferVolume,
        output_base: Path,
        pseudonym: str,
    ) -> None:
        if volume.status == MassTransferVolume.Status.CONVERTED and volume.converted_file:
            return

        if not volume.exported_folder:
            raise DicomError("Missing exported folder for conversion.")

        study_dt = volume.study_datetime
        volume.pseudonym = pseudonym
        series_name = _series_folder_name(
            volume.series_number,
            volume.series_description,
            volume.series_instance_uid,
        )

        subject_id = sanitize_filename(pseudonym or volume.patient_id)
        output_path = _volume_path(output_base, study_dt, subject_id, series_name)
        output_path.mkdir(parents=True, exist_ok=True)

        cmd = [
            "dcm2niix",
            "-z",
            "y",
            "-o",
            str(output_path),
            "-f",
            series_name,
            str(volume.exported_folder),
        ]

        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        combined_output = (result.stdout or "") + (result.stderr or "")

        # dcm2niix returns non-zero when the input contains only non-image
        # DICOM objects (structured reports, presentation states, etc.).
        # This is not an error — there is simply nothing to convert.
        if "No valid DICOM images" in combined_output:
            volume.status = MassTransferVolume.Status.SKIPPED
            volume.add_log("Non-image DICOM series (skipped by dcm2niix)")
            volume.save()
            return

        if result.returncode != 0:
            output = result.stderr or result.stdout
            raise DicomError(
                f"Conversion failed for series {volume.series_instance_uid}: {output}"
            )

        nifti_files = sorted(output_path.glob("*.nii.gz"))
        if not nifti_files:
            raise DicomError(
                f"dcm2niix produced no .nii.gz files for series {volume.series_instance_uid}"
            )

        volume.converted_file = "\n".join(str(f) for f in nifti_files)
        volume.status = MassTransferVolume.Status.CONVERTED
        volume.save()

        self._cleanup_export(volume)

    def _cleanup_export(self, volume: MassTransferVolume) -> None:
        export_folder = volume.exported_folder
        if not export_folder or volume.export_cleaned:
            return

        try:
            shutil.rmtree(export_folder)
        except FileNotFoundError:
            pass
        except Exception as err:
            volume.add_log(f"Cleanup failed: {err}")
            volume.save()
            return

        volume.export_cleaned = True
        volume.save()
