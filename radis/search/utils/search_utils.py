from typing import Protocol, runtime_checkable

from django.db import models

from radis.accounts.models import User
from radis.reports.models import Report


@runtime_checkable
class AnnotatedReport(Protocol):
    total: int


def extract_document_id(id: str) -> str:
    return id.split(":")[-1]


def sanitize_report_summary(text: str) -> str:
    return text.strip()


def get_collection_counts(user: User, document_ids: list[str]) -> dict[str, int]:
    reports = (
        Report.objects.filter(document_id__in=document_ids)
        .annotate(total=models.Count("collections", filter=models.Q(collections__owner=user)))
        .order_by("total")
    )

    collection_counts = {}
    for report in reports:
        assert isinstance(report, AnnotatedReport)
        collection_counts[report.document_id] = report.total

    return collection_counts
