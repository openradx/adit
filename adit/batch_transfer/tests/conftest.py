import pytest

from adit.accounts.factories import GroupFactory
from adit.core.utils.auth_utils import add_permission


@pytest.fixture
def batch_transfer_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "batch_transfer", "add_batchtransferjob")
    add_permission(group, "batch_transfer", "view_batchtransferjob")
    return group
