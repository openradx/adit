from typing import TYPE_CHECKING, Callable, NamedTuple

if TYPE_CHECKING:
    from .models import DicomJob
    from .processors import DicomTaskProcessor


class JobStats(NamedTuple):
    job_name: str
    url_name: str
    counts: dict["DicomJob.Status", int]


JobStatsCollector = Callable[[], JobStats]


job_stats_collectors: list[JobStatsCollector] = []


def register_job_stats_collector(collector: JobStatsCollector) -> None:
    job_stats_collectors.append(collector)


dicom_processors: dict[str, type["DicomTaskProcessor"]] = {}


def register_dicom_processor(model_label: str, dicom_processor: type["DicomTaskProcessor"]) -> None:
    dicom_processors[model_label] = dicom_processor
