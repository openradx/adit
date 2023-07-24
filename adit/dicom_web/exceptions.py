from rest_framework.renderers import JSONRenderer
from rest_framework.views import exception_handler


def dicom_web_exception_handler(exc, context):
    """Switch to JSONRenderer for exceptions"""
    context["request"].accepted_renderer = JSONRenderer()
    return exception_handler(exc, context)
