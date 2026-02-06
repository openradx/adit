from __future__ import annotations

import logging
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from pydicom import Dataset

from adit.core.errors import DicomError
from adit.core.models import DicomNode, DicomTask
from adit.core.processors import DicomTaskProcessor
from adit.core.utils.dicom_dataset import QueryDataset, ResultDataset
from adit.core.utils.dicom_manipulator import DicomManipulator
from adit.core.utils.dicom_operator import DicomOperator
from adit.core.utils.dicom_utils import convert_to_python_regex, write_dataset
from adit.core.utils.sanitize import sanitize_filename

from .models import MassTransferFilter, MassTransferSettings, MassTransferTask, MassTransferVolume

logger = logging.getLogger(__name__)

_MIN_SPLIT_WINDOW = timedelta(minutes=30)


def _dicom_match(pattern: str, value: str | None) -> bool:
    if not pattern:
        return True
    if value is None:
        return False
    regex = convert_to_python_regex(pattern)
    return bool(regex.search(str(value)))


def _parse_int(value: object, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(value)
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


def _volume_export_path(
    base_dir: Path,
    study_dt: datetime,
    subject_id: str,
    series_name: str,
) -> Path:
    year_month = study_dt.strftime("%Y%m")
    return base_dir / year_month / subject_id / series_name


def _volume_output_path(
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

        operator = DicomOperator(source_node.dicomserver)
        volumes = self._find_volumes(operator, filters)

        export_base = _export_base_dir()
        output_base = _destination_base_dir(destination_node)

        converted_count = 0
        failed_count = 0

        volumes_by_study: dict[str, list[MassTransferVolume]] = {}
        for volume in volumes:
            volumes_by_study.setdefault(volume.study_instance_uid, []).append(volume)

        for _, study_volumes in volumes_by_study.items():
            pseudonym = ""
            if job.pseudonymize:
                existing_pseudonym = next(
                    (v.pseudonym for v in study_volumes if v.pseudonym),
                    None,
                )
                pseudonym = existing_pseudonym or uuid.uuid4().hex

            for volume in study_volumes:
                if volume.status == MassTransferVolume.Status.CONVERTED:
                    continue

                try:
                    self._export_volume(operator, volume, export_base, pseudonym)
                    self._convert_volume(volume, output_base, pseudonym)
                    converted_count += 1
                except Exception as err:
                    logger.exception(
                        "Mass transfer failed for volume %s", volume.series_instance_uid
                    )
                    self._cleanup_export(volume)
                    volume.status = MassTransferVolume.Status.ERROR
                    volume.add_log(str(err))
                    volume.save()
                    failed_count += 1

        log_lines = [
            f"Partition {self.mass_task.partition_key}",
            f"Volumes processed: {len(volumes)}",
            f"Converted: {converted_count}",
            f"Failed: {failed_count}",
        ]

        if failed_count and converted_count:
            status = MassTransferTask.Status.WARNING
            message = "Some volumes failed during mass transfer."
        elif failed_count and not converted_count:
            status = MassTransferTask.Status.FAILURE
            message = "All volumes failed during mass transfer."
        else:
            status = MassTransferTask.Status.SUCCESS
            message = "Mass transfer task completed successfully."

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
                    if not created:
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
            return self._find_studies(operator, mf, start, mid) + self._find_studies(
                operator, mf, mid, end
            )

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
        export_path = _volume_export_path(export_base, study_dt, subject_id, series_name)
        export_path.mkdir(parents=True, exist_ok=True)
        volume.exported_folder = str(export_path)

        manipulator = DicomManipulator()

        def callback(ds: Dataset | None) -> None:
            if ds is None:
                return
            manipulator.manipulate(ds, pseudonym=pseudonym)
            file_name = sanitize_filename(f"{ds.SOPInstanceUID}.dcm")
            write_dataset(ds, export_path / file_name)

        operator.fetch_series(
            patient_id=volume.patient_id,
            study_uid=volume.study_instance_uid,
            series_uid=volume.series_instance_uid,
            callback=callback,
        )

        volume.pseudonym = pseudonym
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
        output_path = _volume_output_path(output_base, study_dt, subject_id, series_name)
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
        if result.returncode != 0:
            raise DicomError(
                f"Conversion failed for series {volume.series_instance_uid}: {result.stderr}"
            )

        volume.converted_file = str(output_path / f"{series_name}.nii.gz")
        volume.status = MassTransferVolume.Status.CONVERTED
        volume.save()

        self._cleanup_export(volume)

    def _cleanup_export(self, volume: MassTransferVolume) -> None:
        export_folder = volume.exported_folder
        if not export_folder or export_folder.endswith(" (cleaned)"):
            return

        try:
            shutil.rmtree(export_folder)
        except FileNotFoundError:
            pass
        except Exception as err:
            volume.add_log(f"Cleanup failed: {err}")
            volume.save()
            return

        volume.exported_folder = f"{export_folder} (cleaned)"
        volume.save()
