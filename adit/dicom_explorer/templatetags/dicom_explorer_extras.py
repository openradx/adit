from urllib.parse import urlencode

from django.template import Library
from django.urls import reverse

register = Library()


@register.simple_tag
def explorer_url(
    server_id,
    patient_id=None,
    study_uid=None,
    series_uid=None,
):
    params = {}
    if server_id and not (patient_id or study_uid or series_uid):
        resource_url = reverse(
            "dicom_explorer_server_detail",
            kwargs={
                "server_id": server_id,
            },
        )
    elif server_id and patient_id and not (study_uid or series_uid):
        resource_url = reverse(
            "dicom_explorer_patient_detail",
            kwargs={
                "server_id": server_id,
                "patient_id": patient_id,
            },
        )
    elif server_id and study_uid and not series_uid:
        resource_url = reverse(
            "dicom_explorer_study_detail",
            kwargs={
                "server_id": server_id,
                "study_uid": study_uid,
            },
        )
        if patient_id:
            params["PatientID"] = patient_id
    elif server_id and study_uid and series_uid:
        resource_url = reverse(
            "dicom_explorer_series_detail",
            kwargs={
                "server_id": server_id,
                "study_uid": study_uid,
                "series_uid": series_uid,
            },
        )
        if patient_id:
            params["PatientID"] = patient_id
    else:
        raise ValueError("Invalid DICOM explorer query.")

    if params:
        return f"{resource_url}?{urlencode(params)}"

    return resource_url
