from urllib.parse import urlencode
from django.template import Library

register = Library()


@register.simple_tag
def build_patient_params(server_id, patient_id):
    params = {
        "server": server_id,
        "patient_id": patient_id,
    }
    return urlencode(params)


@register.simple_tag
def build_study_params(server_id, patient_id, study_uid):
    params = {
        "server": server_id,
        "patient_id": patient_id,
        "study_uid": study_uid,
    }
    return urlencode(params)


@register.simple_tag
def build_series_params(server_id, patient_id, study_uid, series_uid):
    params = {
        "server": server_id,
        "patient_id": patient_id,
        "study_uid": study_uid,
        "series_uid": series_uid,
    }
    return urlencode(params)
