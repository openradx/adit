from django.template import Library

register = Library()


@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context):
    return {
        "delete_url": "continuous_transfer_job_delete",
        "verify_url": "continuous_transfer_job_verify",
        "cancel_url": "continuous_transfer_job_cancel",
        "resume_url": "continuous_transfer_job_resume",
        "retry_url": "continuous_transfer_job_retry",
        "restart_url": "continuous_transfer_job_restart",
        "user": context["user"],
        "job": context["job"],
    }
