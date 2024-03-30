import pytest

from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.auth_utils import add_permission


@pytest.fixture
def batch_transfer_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "batch_transfer", "add_batchtransferjob")
    add_permission(group, "batch_transfer", "view_batchtransferjob")
    return group
