from django.conf import settings
from vespa.application import Vespa, VespaAsync
from vespa.package import ApplicationPackage, Field

app_package = ApplicationPackage(name="radis")
schema = app_package.schema
assert schema is not None
schema.add_fields(
    Field(
        name="pacs_aet",
        type="string",
        indexing=["attribute"],
    ),
    Field(
        name="pacs_name",
        type="string",
        indexing=["summary", "attribute"],
    ),
    Field(
        name="patient_id",
        type="string",
        indexing=["summary", "attribute"],
    ),
    Field(
        name="study_uid",
        type="string",
        indexing=["attribute"],
    ),
    Field(
        name="accession_number",
        type="string",
        indexing=["summary", "attribute"],
    ),
    Field(
        name="study_description",
        type="string",
        indexing=["summary", "index"],
    ),
    Field(
        name="study_datetime",
        type="long",
        indexing=["summary", "attribute"],
    ),
    Field(
        name="series_uid",
        type="string",
        indexing=["attribute"],
    ),
    Field(
        name="modalities",
        type="array<string>",
        indexing=["summary", "attribute"],
    ),
    Field(
        name="instance_uid",
        type="string",
        indexing=["attribute"],
    ),
    Field(
        name="references",
        type="array<string>",
        indexing=["summary"],
    ),
    Field(
        name="content",
        type="string",
        indexing=["index"],
    ),
)


def get_vespa_client() -> Vespa:
    vespa_host = settings.VESPA_HOST
    vespa_data_port = settings.VESPA_DATA_PORT
    client = Vespa(f"http://{vespa_host}", vespa_data_port)
    return client


def get_async_vespa_client() -> VespaAsync:
    client = get_vespa_client()
    return client.asyncio()
