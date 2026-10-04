from typing import Any

from django.template import Library

register = Library()


# Router jobs can't be deleted, verified or resumed, so only these actions get URLs.
@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_cancel_url": "router_job_cancel",
        "job_retry_url": "router_job_retry",
        "job_restart_url": "router_job_restart",
        "user": context["user"],
        "job": context["job"],
    }


@register.inclusion_tag("core/_task_detail_control_panel.html", takes_context=True)
def task_control_panel(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_reset_url": "router_task_reset",
        "task_kill_url": "router_task_kill",
        "user": context["user"],
        "task": context["task"],
    }
