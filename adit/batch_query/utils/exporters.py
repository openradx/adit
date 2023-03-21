import csv

from django.conf import settings
from django.utils.formats import date_format, time_format

from adit.core.templatetags.core_extras import join_if_list, person_name_from_dicom

from ..models import BatchQueryJob, BatchQueryResult


def export_results(job: BatchQueryJob, file):
    delimiter = settings.CSV_DELIMITER
    writer = csv.writer(file, delimiter=delimiter)

    query_tasks = job.tasks.prefetch_related("results").all()

    has_pseudonyms = False
    has_series = False
    for query_task in query_tasks:
        if query_task.pseudonym:
            has_pseudonyms = True
        if query_task.series_description or query_task.series_numbers:
            has_series = True
    write_header(writer, has_pseudonyms, has_series)
    write_data(writer, query_tasks, has_pseudonyms, has_series)


def write_header(writer, has_pseudonyms, has_series):
    # TODO: Improve order

    column_headers = [
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
        column_headers.append("Pseudonym")

    if has_series:
        column_headers.extend(
            [
                "SeriesInstanceUID",
                "SeriesDescription",
                "SeriesNumber",
            ]
        )

    writer.writerow(column_headers)


def write_data(writer, query_tasks, has_pseudonyms, has_series):
    for query_task in query_tasks:
        result: BatchQueryResult
        for result in query_task.results.all():
            patient_name = person_name_from_dicom(result.patient_name)

            patient_birth_date = date_format(result.patient_birth_date, "SHORT_DATE_FORMAT")

            study_date = date_format(result.study_date, "SHORT_DATE_FORMAT")

            study_time = time_format(result.study_time, "TIME_FORMAT")

            modalities = ""
            if result.modalities is not None:
                modalities = join_if_list(result.modalities, ", ")

            image_count = ""
            if result.image_count is not None:
                image_count = result.image_count

            csv_row = [
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
                csv_row.append(result.pseudonym)

            if has_series:
                csv_row.extend(
                    [
                        result.series_uid,
                        result.series_description,
                        result.series_number,
                    ]
                )

            writer.writerow(csv_row)
