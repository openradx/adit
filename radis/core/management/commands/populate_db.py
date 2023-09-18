import json
from datetime import datetime, time
from os import environ
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandParser
from faker import Faker

from radis.accounts.factories import AdminUserFactory, InstituteFactory, UserFactory
from radis.accounts.models import Institute, User
from radis.core.vespa_app import vespa_app
from radis.token_authentication.factories import TokenFactory
from radis.token_authentication.models import FRACTION_LENGTH
from radis.token_authentication.utils.crypto import hash_token

USER_COUNT = 20
INSTITUTE_COUNT = 3
ADMIN_AUTH_TOKEN = "f2e7412ca332a85e37f3fce88c6a1904fe35ad63"
INSTITUTES = ["Allgemeinradiologie", "Neuroradiologie", "Thoraxradiologie"]
PACS_ITEMS = [
    {"pacs_aet": "gepacs", "pacs_name": "GE PACS"},
    {"pacs_aet": "synapse", "pacs_name": "Synapse"},
]
MODALITIES = ["CT", "MR", "PET", "CR", "US"]


fake = Faker()


def feed_report(body: str):
    sop_instance_uid = fake.uuid4()
    pacs = fake.random_element(elements=PACS_ITEMS)
    references = [fake.uri() for _ in range(fake.random_int(min=0, max=3))]
    document_id = pacs["pacs_aet"] + "_" + sop_instance_uid
    patient_birth_date = datetime.combine(fake.date_of_birth(), time())
    study_datetime = fake.date_time_between(patient_birth_date, datetime.now())

    response = vespa_app.get_client().feed_data_point(
        schema="report",
        data_id=document_id,
        fields={
            "institutes": fake.random_elements(elements=INSTITUTES, unique=True),
            "pacs_aet": pacs["pacs_aet"],
            "pacs_name": pacs["pacs_name"],
            "patient_id": fake.ean(length=8),
            "patient_birth_date": int(patient_birth_date.timestamp()),
            "patient_sex": fake.random_element(elements=["F", "M", "U"]),
            "study_instance_uid": fake.uuid4(),
            "accession_number": fake.ean(length=13),
            "study_description": fake.sentence(),
            "study_datetime": int(study_datetime.timestamp()),
            "series_instance_uid": fake.uuid4(),
            "modalities_in_study": [fake.random_element(elements=MODALITIES)],
            "sop_instance_uid": sop_instance_uid,
            "references": references,
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


def create_users() -> list[User]:
    if "ADMIN_USERNAME" not in environ or "ADMIN_PASSWORD" not in environ:
        print("Cave! No admin credentials found in environment. Using default ones.")

    admin_data = {
        "username": environ.get("ADMIN_USERNAME", "admin"),
        "first_name": environ.get("ADMIN_FIRST_NAME", "Wilhelm"),
        "last_name": environ.get("ADMIN_LAST_NAME", "Röntgen"),
        "email": environ.get("ADMIN_EMAIL", "wilhelm.roentgen@example.org"),
        "password": environ.get("ADMIN_PASSWORD", "mysecret"),
    }
    admin = AdminUserFactory.create(**admin_data)

    TokenFactory.create(
        token_hashed=hash_token(ADMIN_AUTH_TOKEN),
        fraction=ADMIN_AUTH_TOKEN[:FRACTION_LENGTH],
        owner=admin,
        expires=None,
    )

    users = [admin]

    urgent_permissions = Permission.objects.filter(
        codename="can_process_urgently",
    )
    unpseudonymized_permissions = Permission.objects.filter(
        codename="can_transfer_unpseudonymized",
    )

    user_count = USER_COUNT - 1  # -1 for admin
    for i in range(user_count):
        user = UserFactory.create()

        if i > 0:
            user.user_permissions.add(*urgent_permissions)
            user.user_permissions.add(*unpseudonymized_permissions)

        users.append(user)

    return users


def create_institutes(users: list[User]) -> list[Institute]:
    institutes: list[Institute] = []

    for _ in range(INSTITUTE_COUNT):
        institute = InstituteFactory.create()
        institutes.append(institute)

    for user in users:
        institute: Institute = fake.random_element(elements=institutes)
        institute.users.add(user)

    return institutes


class Command(BaseCommand):
    help = "Populates the database with example data."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--reset", action="store_true")

    def handle(self, *args, **options):
        if options["reset"]:
            # Can only be done when dev server is not running and needs django_extensions installed
            call_command("reset_db", "--noinput")
            call_command("migrate")
            vespa_app.get_client().delete_all_docs("radis_content", "report")

        if User.objects.count() > 0:
            print("Development database already populated. Skipping.")
        else:
            print("Populating development database with test data.")
            users = create_users()
            create_institutes(users)

        results = vespa_app.get_client().query(
            {"yql": "select * from sources * where true", "hits": 1}
        )
        if results.number_documents_retrieved > 0:
            print("Vespa already populated. Skipping.")
        else:
            print("Populating Vespa with example reports.")
            feed_reports()
