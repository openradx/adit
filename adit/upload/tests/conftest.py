import pytest

from adit.accounts.factories import GroupFactory
from adit.core.utils.auth_utils import add_permission


@pytest.fixture
def upload_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "upload", "add_uploadjob")
    return group
