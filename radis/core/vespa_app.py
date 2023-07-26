import xml.etree.ElementTree as ET
from os import PathLike
from pathlib import Path

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


# https://docs.vespa.ai/en/reference/schema-reference.html#bolding
def add_bolding_config(app_folder: PathLike):
    services_file = Path(app_folder) / "services.xml"
    tree = ET.parse(services_file)
    root = tree.getroot()
    container_el = root.find("container")
    assert container_el is not None
    search_el = container_el.find("search")
    assert search_el is not None
    config_el = ET.Element("config", {"name": "container.qr-searchers"})
    search_el.append(config_el)
    tag_el = ET.Element("tag")
    config_el.append(tag_el)
    bold_el = ET.Element("bold")
    tag_el.append(bold_el)
    open_el = ET.Element("open")
    bold_el.append(open_el)
    open_el.text = "<strong>"
    close_el = ET.Element("close")
    bold_el.append(close_el)
    close_el.text = "</strong>"
    separator_el = ET.Element("separator")
    tag_el.append(separator_el)
    separator_el.text = "<em>...</em>"
    ET.indent(tree, "    ")
    tree.write(services_file, encoding="UTF-8", xml_declaration=True)


# https://docs.vespa.ai/en/document-summaries.html#dynamic-snippet-configuration
# https://github.com/vespa-engine/vespa/blob/master/searchsummary/src/vespa/searchsummary/config/juniperrc.def
def add_dynamic_snippet_config(app_folder: PathLike):
    services_file = Path(app_folder) / "services.xml"
    tree = ET.parse(services_file)
    root = tree.getroot()
    content_el = root.find("content")
    assert content_el is not None
    config_el = ET.Element("config", {"name": "vespa.config.search.summary.juniperrc"})
    content_el.append(config_el)
    surround_max_el = ET.Element("length")
    config_el.append(surround_max_el)
    surround_max_el.text = "500"
    ET.indent(tree, "    ")
    tree.write(services_file, encoding="UTF-8", xml_declaration=True)


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
