import pytest
from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.auth_utils import add_permission


@pytest.fixture
def upload_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "upload", "can_upload_data")
    return group
