from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models
from vespa.io import VespaQueryResponse

from radis.core.utils.report_utils import extract_doc_id, sanitize_report_summary

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class CoreSettings(models.Model):
    id: int
    maintenance_mode = models.BooleanField(default=False)
    announcement = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Core settings"

    def __str__(self):
        return f"{self.__class__.__name__} [ID {self.id}]"

    @classmethod
    def get(cls):
        return cls.objects.first()


class AppSettings(models.Model):
    id: int
    # Lock the creation of new jobs
    locked = models.BooleanField(default=False)
    # Suspend the background processing.
    suspended = models.BooleanField(default=False)

    class Meta:
        abstract = True

    @classmethod
    def get(cls):
        return cls.objects.first()


class ReportCollection(models.Model):
    if TYPE_CHECKING:
        reports = RelatedManager["CollectedReport"]()

    id: int
    name = models.CharField(max_length=255, unique=True)
    note = models.TextField(blank=True)
    owner_id: int
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="report_collections",
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Collection "{self.name}"'


class CollectedReport(models.Model):
    id: int
    report_id = models.CharField(max_length=36, unique=True)  # uuid
    note = models.TextField(blank=True)
    collection_id: int
    collection = models.ForeignKey(
        ReportCollection, on_delete=models.CASCADE, related_name="reports"
    )
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Report "{self.report_id}"'


@dataclass(kw_only=True)
class ReportBase:
    doc_id: str
    pacs_name: str
    patient_id: str
    age: int
    gender: str
    accession_number: str
    study_description: str
    study_datetime: datetime
    modalities: list[str]
    references: list[str]
    body: str


@dataclass(kw_only=True)
class ReportSummary(ReportBase):
    relevance: float | None

    @staticmethod
    def from_response(record: dict):
        return ReportSummary(
            relevance=record["relevance"],
            doc_id=extract_doc_id(record["id"]),
            pacs_name=record["fields"]["pacs_name"],
            patient_id=record["fields"]["patient_id"],
            age=record["fields"]["age"],
            gender=record["fields"]["gender"],
            accession_number=record["fields"].get("accession_number", ""),
            study_description=record["fields"].get("study_description", ""),
            study_datetime=record["fields"]["study_datetime"],
            modalities=record["fields"].get("modalities", []),
            references=record["fields"].get("references", []),
            body=sanitize_report_summary(record["fields"]["body"]),
        )


@dataclass(kw_only=True)
class ReportDetail(ReportBase):
    institutes: list[str]
    pacs_aet: str
    study_uid: str
    series_uid: str
    instance_uid: str

    @staticmethod
    def from_response(record: dict):
        return ReportDetail(
            doc_id=extract_doc_id(record["id"]),
            institutes=record["fields"]["institutes"],
            pacs_aet=record["fields"]["pacs_aet"],
            pacs_name=record["fields"]["pacs_name"],
            patient_id=record["fields"]["patient_id"],
            age=record["fields"]["age"],
            gender=record["fields"]["gender"],
            study_uid=record["fields"]["study_uid"],
            accession_number=record["fields"].get("accession_number", ""),
            study_description=record["fields"].get("study_description", ""),
            study_datetime=record["fields"]["study_datetime"],
            series_uid=record["fields"]["series_uid"],
            modalities=record["fields"].get("modalities", []),
            instance_uid=record["fields"]["instance_uid"],
            references=record["fields"].get("references", []),
            body=sanitize_report_summary(record["fields"]["body"]),
        )


@dataclass
class QueryResult:
    total_count: int
    reports: list[ReportSummary]

    @staticmethod
    def from_response(response: VespaQueryResponse):
        return QueryResult(
            total_count=response.json["root"]["fields"]["totalCount"],
            reports=[ReportSummary.from_response(hit) for hit in response.hits],
        )
