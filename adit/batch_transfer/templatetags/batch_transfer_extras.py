from typing import Any

from django.template import Library

from ..models import TransferTask

register = Library()


@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "delete_url": "batch_transfer_job_delete",
        "verify_url": "batch_transfer_job_verify",
        "cancel_url": "batch_transfer_job_cancel",
        "resume_url": "batch_transfer_job_resume",
        "retry_url": "batch_transfer_job_retry",
        "restart_url": "batch_transfer_job_restart",
        "user": context["user"],
        "job": context["job"],
    }


@register.filter
def task_status_badge_class(status: TransferTask.Status) -> str:
    css_classes = {
        TransferTask.Status.PENDING: "badge-secondary",
        TransferTask.Status.IN_PROGRESS: "badge-info",
        TransferTask.Status.CANCELED: "badge-dark",
        TransferTask.Status.SUCCESS: "badge-success",
        TransferTask.Status.WARNING: "badge-warning",
        TransferTask.Status.FAILURE: "badge-danger",
    }
    return css_classes[status]
