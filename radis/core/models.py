from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from django.db import models
from vespa.io import VespaQueryResponse

from .utils.report_utils import extract_document_id, sanitize_report_summary


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
    locked = models.BooleanField(default=False)

    class Meta:
        abstract = True

    @classmethod
    def get(cls):
        return cls.objects.first()


@dataclass(kw_only=True)
class ReportBase:
    document_id: str
    pacs_name: str
    patient_id: str
    patient_birth_date: date
    patient_sex: Literal["F", "M", "U"]
    accession_number: str
    study_description: str
    study_datetime: datetime
    modalities_in_study: list[str]
    references: list[str]
    body: str


@dataclass(kw_only=True)
class ReportSummary(ReportBase):
    relevance: float | None

    @staticmethod
    def from_response(record: dict):
        patient_birth_date = date.fromtimestamp(record["fields"]["patient_birth_date"])
        study_datetime = datetime.fromtimestamp(record["fields"]["study_datetime"])

        return ReportSummary(
            relevance=record["relevance"],
            document_id=extract_document_id(record["id"]),
            pacs_name=record["fields"]["pacs_name"],
            patient_id=record["fields"]["patient_id"],
            patient_birth_date=patient_birth_date,
            patient_sex=record["fields"]["patient_sex"],
            accession_number=record["fields"].get("accession_number", ""),
            study_description=record["fields"].get("study_description", ""),
            study_datetime=study_datetime,
            modalities_in_study=record["fields"].get("modalities_in_study", []),
            references=record["fields"].get("references", []),
            body=sanitize_report_summary(record["fields"]["body"]),
        )


@dataclass(kw_only=True)
class ReportDetail(ReportBase):
    institutes: list[int]
    pacs_aet: str
    study_instance_uid: str
    series_instance_uid: str
    sop_instance_uid: str

    @staticmethod
    def from_response(record: dict):
        patient_birth_date = date.fromtimestamp(record["fields"]["patient_birth_date"])
        study_datetime = datetime.fromtimestamp(record["fields"]["study_datetime"])

        return ReportDetail(
            document_id=extract_document_id(record["id"]),
            institutes=record["fields"]["institutes"],
            pacs_aet=record["fields"]["pacs_aet"],
            pacs_name=record["fields"]["pacs_name"],
            patient_id=record["fields"]["patient_id"],
            patient_birth_date=patient_birth_date,
            patient_sex=record["fields"]["patient_sex"],
            study_instance_uid=record["fields"]["study_instance_uid"],
            accession_number=record["fields"].get("accession_number", ""),
            study_description=record["fields"].get("study_description", ""),
            study_datetime=study_datetime,
            series_instance_uid=record["fields"]["series_instance_uid"],
            modalities_in_study=record["fields"].get("modalities_in_study", []),
            sop_instance_uid=record["fields"]["sop_instance_uid"],
            references=record["fields"].get("references", []),
            body=record["fields"]["body"],
        )


@dataclass
class ReportQueryResult:
    total_count: int
    coverage: float
    documents: int
    reports: list[ReportSummary]

    @staticmethod
    def from_response(response: VespaQueryResponse):
        json = response.json
        return ReportQueryResult(
            total_count=json["root"]["fields"]["totalCount"],
            coverage=json["root"]["coverage"]["coverage"],
            documents=json["root"]["coverage"]["documents"],
            reports=[ReportSummary.from_response(hit) for hit in response.hits],
        )
