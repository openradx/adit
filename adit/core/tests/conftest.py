import pytest

from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.auth_utils import add_permission


@pytest.fixture
def example_transfer_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "example_app", "add_exampletransferjob")
    add_permission(group, "example_app", "view_exampletransferjob")
    return group
