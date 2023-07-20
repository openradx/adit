from django.conf import settings
from vespa.application import Vespa
from vespa.package import (
    ApplicationPackage,
    Document,
    Field,
    FieldSet,
    RankProfile,
    Schema,
    Summary,
)

_report_schema = Schema(
    "report",
    document=Document(
        fields=[
            Field(
                name="organizations",
                type="array<string>",
                indexing=["attribute"],
            ),
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
                name="year_of_birth",
                type="int",
                indexing=["summary", "attribute"],
            ),
            Field(
                name="gender",
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
                indexing=["summary", "index"],
                index="enable-bm25",
                summary=Summary(None, None, ["dynamic"]),
            ),
        ]
    ),
    fieldsets=[
        FieldSet(name="default", fields=["content"]),
    ],
    rank_profiles=[
        RankProfile(name="bm25", first_phase="bm25(content)"),
    ],
)

app_package = ApplicationPackage(name="radis", schema=[_report_schema])


_vespa_host = settings.VESPA_HOST
_vespa_data_port = settings.VESPA_DATA_PORT

vespa_client = Vespa(
    f"http://{_vespa_host}",
    _vespa_data_port,
    application_package=app_package,
)
