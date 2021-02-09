from django.template import Library

register = Library()


@register.inclusion_tag("core/_job_detail_control_panel.html", takes_context=True)
def job_control_panel(context):
    return {
        "delete_url": "batch_query_job_delete",
        "cancel_url": "batch_query_job_cancel",
        "retry_url": "batch_query_job_retry",
        "verify_url": "batch_query_job_verify",
        "user": context["user"],
        "job": context["job"],
    }
