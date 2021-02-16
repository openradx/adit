import re


def person_name_to_dicom(value, add_wildcards=False):
    """ See also :func:`adit.core.templatetags.core_extras.person_name_from_dicom`"""

    if add_wildcards:
        name = value.split(",")
        name = [s.strip() + "*" for s in name]
        return "^".join(name)

    return re.sub(r"\s*,\s*", "^", value)
