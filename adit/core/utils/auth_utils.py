from django.contrib.auth.models import Group

from adit.core.models import DicomNode, DicomNodeGroupAccess


def grant_access(
    group: Group,
    dicom_node: DicomNode,
    source: bool = False,
    destination: bool = False,
) -> None:
    DicomNodeGroupAccess.objects.update_or_create(
        dicom_node=dicom_node,
        group=group,
        defaults={"source": source, "destination": destination},
    )
