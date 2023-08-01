import datetime
import re


def person_name_to_dicom(value: str, add_wildcards=False) -> str:
    """See also :func:`adit.core.templatetags.core_extras.person_name_from_dicom`"""

    if add_wildcards:
        name = value.split(",")
        name = [s.strip() + "*" for s in name]
        return "^".join(name)

    return re.sub(r"\s*,\s*", "^", value)


def format_datetime_attributes(results: list) -> list:
    for instance in results:
        if not instance.get("StudyTime", "") == "":
            instance["StudyTime"] = datetime.datetime.strptime(
                instance["StudyTime"], "%H:%M:%S"
            ).time()
        if not instance.get("StudyDate", "") == "":
            instance["StudyDate"] = datetime.datetime.strptime(instance["StudyDate"], "%Y-%m-%d")
        if not instance.get("PatientBirthDate", "") == "":
            instance["PatientBirthDate"] = datetime.datetime.strptime(
                instance["PatientBirthDate"], "%Y-%m-%d"
            )
    return results
