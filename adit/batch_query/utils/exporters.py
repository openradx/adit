from typing import IO, Any

import pandas as pd

from adit.core.templatetags.core_extras import person_name_from_dicom

from ..models import BatchQueryJob, BatchQueryResult, BatchQueryTask


def write_results(job: BatchQueryJob, file: IO) -> None:
    query_tasks = job.tasks.prefetch_related("results").all()

    has_pseudonyms = False
    has_series = False
    for query_task in query_tasks:
        if query_task.pseudonym:
            has_pseudonyms = True
        if query_task.series_description or query_task.series_numbers:
            has_series = True

    header = get_header(has_pseudonyms, has_series)
    data = []
    for query_task in query_tasks:
        result_rows = get_result_rows(query_task, has_pseudonyms, has_series)
        data += result_rows

    df = pd.DataFrame(data, columns=header)  # type: ignore
    df.to_excel(file, index=False, engine="openpyxl")  # type: ignore


def get_header(has_pseudonyms: bool, has_series: bool) -> list[str]:
    header = []

    if has_pseudonyms:
        header.append("Pseudonym")

    header.extend(
        [
            "PatientID",
            "PatientName",
            "BirthDate",
            "ModalitiesInStudy",
            "StudyDate",
            "StudyTime",
            "StudyDescription",
            "NumberOfStudyRelatedInstances",
            "AccessionNumber",
            "StudyInstanceUID",
        ]
    )

    if has_series:
        header.extend(
            [
                "SeriesInstanceUID",
                "SeriesDescription",
                "SeriesNumber",
            ]
        )

    return header


def get_result_rows(
    query_task: BatchQueryTask, has_pseudonyms: bool, has_series: bool
) -> list[list[Any]]:
    result_rows = []

    result: BatchQueryResult
    for result in query_task.results.all():
        patient_name = person_name_from_dicom(result.patient_name)
        modalities = ", ".join(result.modalities) if result.modalities else ""
        image_count = result.image_count if result.image_count is not None else ""

        result_row = []

        if has_pseudonyms:
            result_row.append(result.pseudonym)

        result_row.extend(
            [
                result.patient_id,
                patient_name,
                result.patient_birth_date,
                modalities,
                result.study_date,
                result.study_time,
                result.study_description,
                image_count,
                result.accession_number,
                result.study_uid,
            ]
        )

        if has_series:
            result_row.extend(
                [
                    result.series_uid,
                    result.series_description,
                    result.series_number,
                ]
            )

        result_rows.append(result_row)

    return result_rows
