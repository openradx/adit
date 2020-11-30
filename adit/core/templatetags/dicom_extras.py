from datetime import datetime
from django.template import Library

register = Library()


@register.filter(expects_localtime=True)
def parse_dicom_date(value):
    return datetime.strptime(value, "%Y%m%d")


@register.filter
def convert_dicom_person_name(value):
    return value.replace("^", ", ")


@register.filter
def filter_modalities(value):
    exclude = ["SR", "PR"]

    if isinstance(value, list):
        return [modality for modality in value if modality not in exclude]

    if value in exclude:
        return ""

    return value
