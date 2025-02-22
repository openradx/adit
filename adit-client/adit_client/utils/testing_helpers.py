from adit_radis_shared.accounts.models import User
from adit_radis_shared.common.utils.testing_helpers import add_user_to_group
from adit_radis_shared.token_authentication.models import Token
from django.contrib.auth.models import Group


def create_admin_with_group_and_token():
    user: User = User.objects.create_superuser("admin")
    group = Group.objects.create(name="Staff")
    add_user_to_group(user, group)
    _, token = Token.objects.create_token(user, "", None)
    return user, group, token
