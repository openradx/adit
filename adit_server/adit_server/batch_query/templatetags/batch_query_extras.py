from typing import Any

from django.template import Library

register = Library()


@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_delete_url": "batch_query_job_delete",
        "job_verify_url": "batch_query_job_verify",
        "job_cancel_url": "batch_query_job_cancel",
        "job_resume_url": "batch_query_job_resume",
        "job_retry_url": "batch_query_job_retry",
        "job_restart_url": "batch_query_job_restart",
        "user": context["user"],
        "job": context["job"],
    }


@register.inclusion_tag("core/_task_detail_control_panel.html", takes_context=True)
def task_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_delete_url": "batch_query_task_delete",
        "task_reset_url": "batch_query_task_reset",
        "task_kill_url": "batch_query_task_kill",
        "user": context["user"],
        "task": context["task"],
    }
