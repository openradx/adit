from datetime import datetime
from django.template import Library

register = Library()


@register.filter(expects_localtime=True)
def parse_dicom_date(value):
    return datetime.strptime(value, "%Y%m%d")


@register.filter
def convert_dicom_person_name(value):
    return value.replace("^", ", ")