from typing import Any

from django.template import Library

register = Library()


@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_delete_url": "batch_transfer_job_delete",
        "job_verify_url": "batch_transfer_job_verify",
        "job_cancel_url": "batch_transfer_job_cancel",
        "job_resume_url": "batch_transfer_job_resume",
        "job_retry_url": "batch_transfer_job_retry",
        "job_restart_url": "batch_transfer_job_restart",
        "user": context["user"],
        "job": context["job"],
    }


@register.inclusion_tag("core/_task_detail_control_panel.html", takes_context=True)
def task_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_delete_url": "batch_transfer_task_delete",
        "task_reset_url": "batch_transfer_task_reset",
        "task_kill_url": "batch_transfer_task_kill",
        "user": context["user"],
        "task": context["task"],
    }
