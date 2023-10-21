import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from typing import Literal

from rest_framework.status import HTTP_200_OK
from vespa.io import VespaQueryResponse

from radis.api.site import ReportEventType
from radis.core.models import AppSettings
from radis.reports.models import Report

from .utils.search_utils import extract_document_id, sanitize_report_summary
from .vespa_app import REPORT_SCHEMA_NAME, vespa_app

logger = logging.getLogger(__name__)


class SearchAppSettings(AppSettings):
    class Meta:
        verbose_name_plural = "Search app settings"


@dataclass(kw_only=True)
class ReportDocument:
    document_id: str
    institutes: list[int]
    pacs_aet: str
    pacs_name: str
    patient_birth_date: date
    patient_sex: Literal["F", "M", "U"]
    study_description: str
    study_datetime: datetime
    modalities_in_study: list[str]
    references: list[str]
    body: str

    @staticmethod
    def from_report_model(report: Report):
        assert report.patient_sex in ("M", "F", "U")

        return ReportDocument(
            document_id=report.document_id,
            institutes=[institute.id for institute in report.institutes.all()],
            pacs_aet=report.pacs_aet,
            pacs_name=report.pacs_name,
            patient_birth_date=report.patient_birth_date,
            patient_sex=report.patient_sex,
            study_description=report.study_description,
            study_datetime=report.study_datetime,
            modalities_in_study=report.modalities_in_study,
            references=report.references,
            body=sanitize_report_summary(report.body),
        )

    def dictify_for_vespa(self):
        fields = asdict(self)

        # Vespa can't store dates and datetimes natively, so we store them as a number,
        # see also schema in vespa_app.py
        fields["patient_birth_date"] = int(
            datetime.combine(fields["patient_birth_date"], time()).timestamp()
        )
        fields["study_datetime"] = int(fields["study_datetime"].timestamp())

        return fields

    def create(self):
        fields = self.dictify_for_vespa()
        del fields["document_id"]
        response = vespa_app.get_client().feed_data_point(
            REPORT_SCHEMA_NAME, self.document_id, fields
        )
        # TODO: improve error handling
        if response.get_status_code() != HTTP_200_OK:
            message = response.get_json()
            raise Exception(f"Error while feeding report to Vespa: {message}")

    def update(self):
        fields = self.dictify_for_vespa()
        del fields["document_id"]
        response = vespa_app.get_client().update_data("report", self.document_id, fields)
        # TODO: improve error handling
        if response.get_status_code() != HTTP_200_OK:
            message = response.get_json()
            raise Exception(f"Error while updating report on Vespa: {message}")

    def delete(self):
        response = vespa_app.get_client().delete_data("report", self.document_id)
        # TODO: improve error handling
        if response.get_status_code() != HTTP_200_OK:
            message = response.get_json()
            raise Exception(f"Error while deleting report on Vespa: {message}")


@dataclass(kw_only=True)
class ReportSummary:
    relevance: float | None
    document_id: str
    pacs_name: str
    patient_birth_date: date
    patient_sex: Literal["F", "M", "U"]
    study_description: str
    study_datetime: datetime
    modalities_in_study: list[str]
    references: list[str]
    body: str

    @staticmethod
    def from_vespa_response(record: dict):
        patient_birth_date = date.fromtimestamp(record["fields"]["patient_birth_date"])
        study_datetime = datetime.fromtimestamp(record["fields"]["study_datetime"])

        return ReportSummary(
            relevance=record["relevance"],
            document_id=extract_document_id(record["id"]),
            pacs_name=record["fields"]["pacs_name"],
            patient_birth_date=patient_birth_date,
            patient_sex=record["fields"]["patient_sex"],
            study_description=record["fields"].get("study_description", ""),
            study_datetime=study_datetime,
            modalities_in_study=record["fields"].get("modalities_in_study", []),
            references=record["fields"].get("references", []),
            body=sanitize_report_summary(record["fields"]["body"]),
        )


@dataclass
class ReportQuery:
    total_count: int
    coverage: float
    documents: int
    reports: list[ReportSummary]

    @staticmethod
    def from_vespa_response(response: VespaQueryResponse):
        json = response.json
        return ReportQuery(
            total_count=json["root"]["fields"]["totalCount"],
            coverage=json["root"]["coverage"]["coverage"],
            documents=json["root"]["coverage"]["documents"],
            reports=[ReportSummary.from_vespa_response(hit) for hit in response.hits],
        )

    @staticmethod
    def query_reports(query: str, offset: int = 0, page_size: int = 100) -> "ReportQuery":
        client = vespa_app.get_client()
        response = client.query(
            {
                "yql": "select * from report where userQuery()",
                "query": query,
                "type": "web",
                "hits": page_size,
                "offset": offset,
            }
        )
        return ReportQuery.from_vespa_response(response)


def handle_report(event_type: ReportEventType, report: Report):
    # Sync reports with Vespa
    if event_type == "created":
        ReportDocument.from_report_model(report).create()
    elif event_type == "updated":
        ReportDocument.from_report_model(report).update()
    elif event_type == "deleted":
        ReportDocument.from_report_model(report).delete()
