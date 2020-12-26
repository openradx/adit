import csv
from ..models import BatchFinderJob


def export_results(job: BatchFinderJob, file):
    writer = csv.writer(file, delimiter=";")

    # Write column header
    writer.writerow(
        [
            "Batch ID",
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

    # Write data
    for query in job.queries.prefetch_related("results").all():
        for result in query.results.all():
            modalities = ""
            if result.modalities:
                modalities = ",".join(result.modalities)

            image_count = ""
            if result.image_count is not None:
                image_count = result.image_count

            csv_row = [
                query.batch_id,
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
            writer.writerow(csv_row)
