from django.template import Library

from ..models import TransferTask

register = Library()


@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context):
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
def task_status_badge_class(status):
    css_class = ""
    if status == TransferTask.Status.PENDING:
        css_class = "text-bg-secondary"
    elif status == TransferTask.Status.IN_PROGRESS:
        css_class = "text-bg-info"
    elif status == TransferTask.Status.CANCELED:
        css_class = "text-bg-dark"
    elif status == TransferTask.Status.SUCCESS:
        css_class = "text-bg-success"
    elif status == TransferTask.Status.WARNING:
        css_class = "text-bg-warning"
    elif status == TransferTask.Status.FAILURE:
        css_class = "text-bg-danger"
    return css_class
