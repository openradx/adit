import pytest

from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.auth_utils import add_permission


@pytest.fixture
def batch_query_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "batch_query", "add_batchqueryjob")
    add_permission(group, "batch_query", "view_batchqueryjob")
    return group
