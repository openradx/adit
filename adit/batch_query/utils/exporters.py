from typing import IO

import pandas as pd
from django.utils.formats import date_format, time_format

from adit.core.templatetags.core_extras import join_if_list, person_name_from_dicom

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

    df = pd.DataFrame(data, columns=header)
    df.to_excel(file, index=False)


def get_header(has_pseudonyms: bool, has_series: bool) -> list[str]:
    # TODO: Improve order

    header = [
        "PatientID",
        "PatientName",
        "BirthDate",
        "AccessionNumber",
        "StudyDate",
        "StudyTime",
        "ModalitiesInStudy",
        "NumberOfStudyRelatedInstances",
        "StudyDescription",
        "StudyInstanceUID",
    ]

    if has_pseudonyms:
        header.append("Pseudonym")

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
) -> list[list[str]]:
    result_rows = []

    result: BatchQueryResult
    for result in query_task.results.all():
        patient_name = person_name_from_dicom(result.patient_name)

        # TODO: check if we can use datetime directly (without string conversion)
        patient_birth_date = date_format(result.patient_birth_date, "SHORT_DATE_FORMAT")
        study_date = date_format(result.study_date, "SHORT_DATE_FORMAT")
        study_time = time_format(result.study_time, "TIME_FORMAT")

        modalities = ""
        if result.modalities is not None:
            modalities = join_if_list(result.modalities, ", ")

        image_count = ""
        if result.image_count is not None:
            image_count = result.image_count

        result_row = [
            result.patient_id,
            patient_name,
            patient_birth_date,
            study_date,
            study_time,
            result.study_description,
            modalities,
            image_count,
            result.accession_number,
            result.study_uid,
        ]

        if has_pseudonyms:
            result_row.append(result.pseudonym)

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
