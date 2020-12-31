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
    if patient_id and not study_uid:
        resource_url = reverse(
            "dicom_explorer_query_patients",
            kwargs={
                "server_id": server_id,
                "patient_id": patient_id,
            },
        )
    elif study_uid and not series_uid:
        resource_url = reverse(
            "dicom_explorer_query_studies",
            kwargs={
                "server_id": server_id,
                "study_uid": study_uid,
            },
        )
        if patient_id:
            params["PatientID"] = patient_id
    elif study_uid and series_uid:
        resource_url = reverse(
            "dicom_explorer_query_series",
            kwargs={
                "server_id": server_id,
                "study_uid": study_uid,
                "series_uid": series_uid,
            },
        )
        if patient_id:
            params["PatientID"] = patient_id

    else:
        # Should never happen as we validate the form
        raise AssertionError("Invalid DICOM explorer query.")

    return "%s?%s" % (resource_url, urlencode(params))
