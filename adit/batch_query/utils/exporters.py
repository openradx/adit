import csv
from django.utils.formats import date_format, time_format
from adit.core.templatetags.core_extras import person_name_from_dicom, join_if_list
from ..models import BatchQueryJob, BatchQueryResult


def export_results(job: BatchQueryJob, file):
    writer = csv.writer(file, delimiter=";")

    # Write column header
    writer.writerow(
        [
            "BatchID",
            "PatientID",
            "PatientName",
            "BirthDate",
            "StudyDate",
            "StudyTime",
            "StudyDescription",
            "Modalities",
            "ImageCount",
            "AccessionNumber",
            "StudyInstanceUID",
        ]
    )

    # Write data
    for query in job.queries.prefetch_related("results").all():
        result: BatchQueryResult
        for result in query.results.all():
            patient_name = person_name_from_dicom(result.patient_name)

            patient_birth_date = date_format(
                result.patient_birth_date, "SHORT_DATE_FORMAT"
            )

            study_date = date_format(result.study_date, "SHORT_DATE_FORMAT")

            study_time = time_format(result.study_time, "TIME_FORMAT")

            modalities = ""
            if modalities is not None:
                modalities = join_if_list(modalities, ",")

            image_count = ""
            if result.image_count is not None:
                image_count = result.image_count

            csv_row = [
                query.batch_id,
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
            writer.writerow(csv_row)
