import csv
from ..models import StudyFinderJob


def _create_csv_row(query, result):
    modalities = ""
    if result.modalities:
        modalities = ",".join(result.modalities)

    image_count = ""
    if result.image_count is not None:
        image_count = result.image_count

    return [
        query.row_id,
        result.patient_id,
        result.patient_name,
        result.patient_birth_date,
        result.study_date,
        result.study_description,
        modalities,
        image_count,
        result.accession_number,
        result.study_uid,
    ]


def export_results(job: StudyFinderJob, file):
    writer = csv.writer(file)
    writer.writerow(
        [
            "Row ID",
            "Patient ID",
            "Patient Name",
            "Birth Date",
            "Study Date",
            "Study Description",
            "Modalities",
            "Image Count",
            "Accession Number",
            "Study UID",
        ]
    )

    for query in job.queries.prefetch_related("results"):
        for result in query.results:
            csv_row = _create_csv_row(query, result)
            writer.writerow(csv_row)
