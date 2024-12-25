from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.testing_helpers import add_permission
from django.conf import settings


def create_upload_group():
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "upload", "can_upload_data")
    return group


def get_sample_dicoms_folder(patient_id: str) -> str:
    return settings.BASE_DIR / "samples" / "dicoms" / patient_id
