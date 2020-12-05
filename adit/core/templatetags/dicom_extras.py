from datetime import datetime
from django.template import Library

register = Library()


@register.filter
def parse_dicom_date(value):
    if not value:
        return value

    return datetime.strptime(value, "%Y%m%d")


@register.filter
def parse_dicom_time(value):
    # http://dicom.nema.org/dicom/2013/output/chtml/part05/sect_6.2.html
    if not value:
        return value

    time_formats = ["%H", "%H%M", "%H%M%S", "%H%M%S.%f"]
    time = None
    for time_format in time_formats:
        try:
            time = datetime.strptime(value, time_format)
        except ValueError:
            pass

    if not time:
        raise ValueError(f"Invalid DICOM time representation: {value}")

    return time.time()


@register.simple_tag
def parse_dicom_datetime(date_value, time_value):
    if not date_value:
        return date_value

    date = parse_dicom_date(date_value)
    time = parse_dicom_time(time_value)

    if not time:
        return date

    return datetime.combine(date, time)


@register.filter
def convert_dicom_person_name(value):
    if not value:
        return value

    return value.replace("^", ", ")


@register.filter
def filter_modalities(value):
    if not value:
        return value

    exclude = ["SR", "PR"]

    if isinstance(value, list):
        return [modality for modality in value if modality not in exclude]

    if value in exclude:
        return ""

    return value
