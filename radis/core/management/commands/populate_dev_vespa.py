import json
from pathlib import Path

import shortuuid
from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from faker import Faker

from radis.core.vespa_app import vespa_app

fake = Faker()

organizations = ["allrad", "neurorad", "thoraxrad"]
pacs_items = [
    {"pacs_aet": "gepacs", "pacs_name": "GE PACS"},
    {"pacs_aet": "synapse", "pacs_name": "Synapse"},
]
modalities = ["CT", "MR", "PET", "CR", "US"]


def feed_report(body: str):
    data_id = shortuuid.uuid()
    pacs = fake.random_element(elements=pacs_items)

    response = vespa_app.get_client().feed_data_point(
        schema="report",
        data_id=data_id,
        fields={
            "organizations": fake.random_elements(elements=organizations, unique=True),
            "pacs_aet": pacs["pacs_aet"],
            "pacs_name": pacs["pacs_name"],
            "patient_id": fake.ean(length=8),
            "year_of_birth": int(fake.year()),
            "gender": fake.random_element(elements=["F", "M"]),
            "study_uid": fake.uuid4(),
            "accession_number": fake.ean(length=13),
            "study_description": fake.sentence(),
            "study_datetime": int(fake.date_time_between().timestamp()),
            "series_uid": fake.uuid4(),
            "modalities": [fake.random_element(elements=modalities)],
            "instance_uid": fake.uuid4(),
            "references": [],
            "body": body,
        },
    )

    if response.get_status_code() != 200:
        raise AssertionError


def feed_reports():
    samples_path = Path(settings.BASE_DIR / "samples" / "reports.json")
    with open(samples_path, "r") as f:
        reports = json.load(f)

    for report in reports:
        feed_report(report)


class Command(BaseCommand):
    help = "Populates Vespa with example reports."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        if options["reset"]:
            print("Resetting Vespa.")
            # pyvespa creates a content cluster name by using the app name
            # and adding the suffix "_content"
            vespa_app.get_client().delete_all_docs("radis_content", "report")

        results = vespa_app.get_client().query(
            {"yql": "select * from sources * where true", "hits": 1}
        )
        if results.number_documents_retrieved > 0:
            print("Vespa already populated. Skipping.")
        else:
            print("Populating Vespa with example reports.")
            feed_reports()
