import pytest

from adit.accounts.factories import GroupFactory
from adit.core.utils.auth_utils import add_permission


@pytest.fixture
def batch_query_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "batch_query", "add_batchqueryjob")
    add_permission(group, "batch_query", "view_batchqueryjob")
    return group
