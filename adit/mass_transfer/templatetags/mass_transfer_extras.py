from typing import Any

from django.template import Library

from ..models import MassTransferVolume

register = Library()


@register.filter
def volume_status_css_class(status: str) -> str:
    css_classes = {
        MassTransferVolume.Status.PENDING: "text-secondary",
        MassTransferVolume.Status.EXPORTED: "text-info",
        MassTransferVolume.Status.CONVERTED: "text-success",
        MassTransferVolume.Status.SKIPPED: "text-muted",
        MassTransferVolume.Status.ERROR: "text-danger",
    }
    return css_classes.get(status, "text-secondary")


@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_delete_url": "mass_transfer_job_delete",
        "job_verify_url": "mass_transfer_job_verify",
        "job_cancel_url": "mass_transfer_job_cancel",
        "job_resume_url": "mass_transfer_job_resume",
        "job_retry_url": "mass_transfer_job_retry",
        "job_restart_url": "mass_transfer_job_restart",
        "user": context["user"],
        "job": context["job"],
    }


@register.inclusion_tag("core/_task_detail_control_panel.html", takes_context=True)
def task_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_delete_url": "mass_transfer_task_delete",
        "task_reset_url": "mass_transfer_task_reset",
        "task_kill_url": "mass_transfer_task_kill",
        "user": context["user"],
        "task": context["task"],
    }
