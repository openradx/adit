import pytest

from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.auth_utils import add_permission


@pytest.fixture
def dicom_web_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "dicom_web", "can_query")
    add_permission(group, "dicom_web", "can_retrieve")
    add_permission(group, "dicom_web", "can_store")
    return group
