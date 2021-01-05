import re


def person_name_to_dicom(value):
    """ See also :func:`adit.core.templatetags.core_extras.person_name_from_dicom`"""
    return re.sub(r"\s*,\s*", "^", value)
