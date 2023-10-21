import re
from typing import cast

from django.db import models

from radis.accounts.models import User
from radis.reports.models import Report


def extract_document_id(id: str) -> str:
    return id.split(":")[-1]


def sanitize_report_summary(text: str) -> str:
    text = re.sub(r"[\r\n]+", '<em class="break">...</em>', text)
    return text.strip()


class ReportWithAnnotation(Report):
    total: int


def get_collection_counts(user: User, document_ids: list[str]) -> dict[str, int]:
    reports = (
        Report.objects.filter(document_id__in=document_ids)
        .annotate(total=models.Count("collections", filter=models.Q(collections__owner=user)))
        .order_by("total")
    )

    return {report.document_id: cast(ReportWithAnnotation, report).total for report in reports}
