import xml.etree.ElementTree as ET
from os import PathLike
from pathlib import Path

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

REPORT_SCHEMA_NAME = "report"


def _create_report_schema():
    return Schema(
        REPORT_SCHEMA_NAME,
        document=Document(
            fields=[
                Field(
                    name="groups",
                    type="array<int>",
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
                    indexing=["summary"],
                ),
                Field(
                    name="patient_birth_date",
                    type="int",
                    indexing=["summary", "attribute"],
                ),
                Field(
                    name="patient_sex",
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
                    name="modalities_in_study",
                    type="array<string>",
                    indexing=["summary", "attribute"],
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


class VespaConfigurator:
    def __init__(self, app_folder: PathLike) -> None:
        self.services_file = Path(app_folder) / "services.xml"
        self.services_doc = ET.parse(self.services_file)

    # https://docs.vespa.ai/en/reference/schema-reference.html#bolding
    def _add_bolding_config(self):
        config_el = ET.fromstring(
            """
            <config name="container.qr-searchers">
                <tag>
                    <bold>
                        <open>&lt;strong&gt;</open>
                        <close>&lt;/strong&gt;</close>
                    </bold>
                    <separator>&lt;em&gt;...&lt;/em&gt;</separator>
                </tag>
            </config>
        """
        )
        search_el = self.services_doc.find("./container/search")
        assert search_el is not None
        search_el.append(config_el)

    # https://docs.vespa.ai/en/document-summaries.html#dynamic-snippet-configuration
    # https://github.com/vespa-engine/vespa/blob/master/searchsummary/src/vespa/searchsummary/config/juniperrc.def
    def _add_dynamic_snippet_config(self):
        config_el = ET.fromstring(
            """
            <config name="vespa.config.search.summary.juniperrc">
                <length>500</length>
            </config>
        """
        )
        content_el = self.services_doc.find("./content")
        assert content_el is not None
        content_el.append(config_el)

    def _write(self):
        ET.indent(self.services_doc, "    ")
        self.services_doc.write(self.services_file, encoding="UTF-8", xml_declaration=True)

    def apply(self):
        self._add_bolding_config()
        self._add_dynamic_snippet_config()
        self._write()


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


vespa_app = VespaApp()
