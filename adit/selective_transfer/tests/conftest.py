import pytest

from adit.accounts.factories import GroupFactory
from adit.core.utils.auth_utils import add_permission


@pytest.fixture
def selective_transfer_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "selective_transfer", "add_selectivetransferjob")
    add_permission(group, "selective_transfer", "view_selectivetransferjob")
    return group
