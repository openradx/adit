from urllib.parse import urlencode

import django_tables2 as tables
from django.db.models import Count, Max, Q, QuerySet
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from adit.core.tables import RecordIdColumn, TransferJobTable
from adit.core.templatetags.core_extras import dicom_job_status_css_class

from .models import RouterJob, RouterTask, RoutingRule

# Router jobs start pending, so they are never unverified.
DELIVERY_STATUSES = [status for status in RouterJob.Status if status != RouterJob.Status.UNVERIFIED]


def with_deliveries(rules: QuerySet[RoutingRule]) -> QuerySet[RoutingRule]:
    """Annotate each rule with its delivery counts by status and its last match."""
    counts = {
        f"deliveries_{status.value}": Count("jobs", filter=Q(jobs__status=status))
        for status in DELIVERY_STATUSES
    }
    return rules.annotate(last_match=Max("jobs__created"), **counts)


class RoutingRuleTable(tables.Table):
    name = tables.Column(linkify=True)
    enabled = tables.Column(verbose_name="On/Off")
    destination = tables.Column()
    pseudonymize = tables.Column(verbose_name="Pseudonymizes")
    deliveries = tables.Column(empty_values=(), orderable=False)
    last_match = tables.DateTimeColumn(verbose_name="Last Match", default="—")

    class Meta:
        model = RoutingRule
        fields = ("name", "enabled", "destination", "pseudonymize", "deliveries", "last_match")
        empty_text = "No routing rules yet"
        attrs = {"class": "table table-bordered table-hover"}

    def render_enabled(self, value: bool) -> str:
        css_class, label = ("text-success", "On") if value else ("text-muted", "Off")
        return format_html('<span class="{}">{}</span>', css_class, label)

    def render_pseudonymize(self, value: bool) -> str:
        return "Yes" if value else "No"

    def render_deliveries(self, record: RoutingRule) -> str:
        job_list_url = reverse("router_job_list")
        links = format_html_join(
            " ",
            '<a href="{}" class="{} text-nowrap">{} {}</a>',
            (
                (
                    f"{job_list_url}?{urlencode({'rule': record.pk, 'status': status.value})}",
                    dicom_job_status_css_class(status),
                    status.label,
                    count,
                )
                for status in DELIVERY_STATUSES
                if (count := getattr(record, f"deliveries_{status.value}"))
            ),
        )
        return links or "—"


class RoutingRuleJobTable(tables.Table):
    id = RecordIdColumn(verbose_name="Job ID")
    closed_at = tables.DateTimeColumn(accessor="batch__closed_at", verbose_name="Closed At")
    patient_id = tables.Column(empty_values=(), orderable=False, verbose_name="Patient ID")
    pseudonym = tables.Column(empty_values=(), orderable=False)
    study = tables.Column(accessor="batch__study_instance_uid", verbose_name="Study Instance UID")
    images_sent = tables.Column(empty_values=(), orderable=False, verbose_name="Images Sent")

    class Meta:
        model = RouterJob
        fields = ("id", "closed_at", "patient_id", "pseudonym", "study", "images_sent", "status")
        empty_text = "No deliveries yet"
        attrs = {"class": "table table-bordered table-hover"}

    def render_patient_id(self, record: RouterJob) -> str:
        task = _delivery_task(record)
        return task.patient_id if task else "—"

    def render_pseudonym(self, record: RouterJob) -> str:
        task = _delivery_task(record)
        return task.pseudonym if task and task.pseudonym else "—"

    def render_images_sent(self, record: RouterJob) -> int | str:
        # The sent lists are cleared after ROUTER_SENT_LIST_RETENTION_DAYS.
        task = _delivery_task(record)
        return len(task.sent_instance_uids) if task and task.sent_instance_uids else "—"

    def render_status(self, value: str, record: RouterJob) -> str:
        css_class = dicom_job_status_css_class(record.status)
        return format_html('<span class="{} text-nowrap">{}</span>', css_class, value)


def _delivery_task(job: RouterJob) -> RouterTask | None:
    # The view prefetches the tasks; a router job has exactly one.
    return next(iter(job.tasks.all()), None)


class RouterJobTable(TransferJobTable):
    rule = tables.Column(linkify=True)

    class Meta(TransferJobTable.Meta):
        model = RouterJob
        fields = ("id", "rule", "status", "message", "created")
        empty_text = "No router jobs to show"
