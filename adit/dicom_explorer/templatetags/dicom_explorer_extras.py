from urllib.parse import urlencode
from django.template import Library

register = Library()


@register.simple_tag
def build_study_params(study):
    params = {
        "query": "1",
        "patient_id": study["PatientID"],
        "study_uid": study["StudyInstanceUID"],
    }
    return urlencode(params)
