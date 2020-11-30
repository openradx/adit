from django.template import Library
from ..models import TransferTask

register = Library()


@register.filter
def transfer_task_status_text_class(status):
    if status == TransferTask.Status.SUCCESS:
        return "text-success"

    return ""
