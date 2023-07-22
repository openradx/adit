from django.conf import settings
from vespa.application import Vespa
from vespa.io import VespaQueryResponse
from vespa.package import (
    ApplicationPackage,
    Document,
    Field,
    FieldSet,
    RankProfile,
    Schema,
    Summary,
)


def _create_report_schema():
    return Schema(
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
                    name="body",
                    type="string",
                    indexing=["summary", "index"],
                    index="enable-bm25",
                    summary=Summary(None, None, ["dynamic"]),
                ),
            ]
        ),
        fieldsets=[
            FieldSet(name="default", fields=["body"]),
        ],
        rank_profiles=[
            RankProfile(name="default", first_phase="bm25(body)"),
        ],
    )


def _create_app_package(schemas: list[Schema]):
    return ApplicationPackage(name="radis", schema=schemas)


class VespaApp:
    _vespa_host = settings.VESPA_HOST
    _vespa_data_port = settings.VESPA_DATA_PORT

    _app_package: ApplicationPackage | None = None
    _client: Vespa | None = None

    def get_app_package(self) -> ApplicationPackage:
        if not self._app_package:
            report_schema = _create_report_schema()
            self._app_package = _create_app_package([report_schema])
        return self._app_package

    def get_client(self) -> Vespa:
        if not self._client:
            self._client = Vespa(
                f"http://{self._vespa_host}",
                self._vespa_data_port,
                application_package=self.get_app_package(),
            )
        return self._client

    async def query_reports(
        self, query: str, page_number: int = 1, page_size: int = 100
    ) -> VespaQueryResponse:
        offset = (page_number - 1) * page_size

        async with self.get_client().asyncio() as client:
            # TODO: filter organizations
            return await client.query(
                {
                    "yql": "select * from report where userQuery()",
                    "query": query,
                    "type": "web",
                    "hits": page_size,
                    "offset": offset,
                }
            )


vespa_app = VespaApp()
