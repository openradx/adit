from urllib.parse import urlencode
from django.template import Library
from django.urls import reverse

register = Library()


@register.simple_tag
def explorer_url(
    server,
    patient_id=None,
    study_uid=None,
    accession_number=None,
    series_uid=None,
):
    params = {"server": server}

    if patient_id is not None:
        params["patient_id"] = patient_id

    if study_uid is not None:
        params["study_uid"] = study_uid

    if accession_number is not None:
        params["accession_number"] = accession_number

    if series_uid is not None:
        params["series_uid"] = series_uid

    return "%s?%s" % reverse("dicom_explorer"), urlencode(params)
