import pytest

from adit.accounts.factories import GroupFactory
from adit.core.utils.auth_utils import add_permission


@pytest.fixture
def token_authentication_group(db):
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "token_authentication", "add_token")
    add_permission(group, "token_authentication", "delete_token")
    add_permission(group, "token_authentication", "view_token")
    return group
