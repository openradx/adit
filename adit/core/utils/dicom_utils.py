import datetime
import re
from typing import List

from pydicom import Sequence
from pydicom.dataset import Dataset


def person_name_to_dicom(value, add_wildcards=False):
    """See also :func:`adit.core.templatetags.core_extras.person_name_from_dicom`"""

    if add_wildcards:
        name = value.split(",")
        name = [s.strip() + "*" for s in name]
        return "^".join(name)

    return re.sub(r"\s*,\s*", "^", value)


def format_datetime_attributes(results: List) -> List:
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


def adit_dict_to_dicom_json(dict_list: List) -> List:
    list = []
    for dict in dict_list:
        ds = Dataset()
        for key, value in dict.items():
            try:
                setattr(ds, key, value)
            except TypeError:
                try:
                    for seq_value in value:
                        seq = Sequence()
                        for seq_key, seq_value in seq_value.items():
                            seq_ds = Dataset()
                            setattr(seq_ds, seq_key, seq_value)
                            seq.append(seq_ds)
                        setattr(ds, key, seq)
                except Exception as e:
                    raise Exception(e)
        ds = strftime_dataset(ds)
        list.append(ds.to_json(suppress_invalid_tags=True))
    return list


def strftime_dataset(ds: Dataset) -> Dataset:
    for elem in ds:
        if elem.VR == "DA":
            elem.value = elem.value.strftime("%Y%m%d")
        elif elem.VR == "TM":
            elem.value = elem.value.strftime("%H%M%S")
        elif elem.VR == "DT":
            elem.value = elem.value.strftime("%Y%m%d%H%M%S")
    return ds
