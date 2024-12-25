from adit_radis_shared.accounts.factories import GroupFactory, UserFactory
from adit_radis_shared.common.utils.testing_helpers import add_permission, add_user_to_group
from adit_radis_shared.token_authentication.models import Token


def create_dicom_web_group():
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "dicom_web", "can_query")
    add_permission(group, "dicom_web", "can_retrieve")
    add_permission(group, "dicom_web", "can_store")
    return group


def create_user_with_dicom_web_group_and_token():
    user = UserFactory.create()
    group = create_dicom_web_group()
    add_user_to_group(user, group)
    _, token_string = Token.objects.create_token(user, "", None)
    return user, group, token_string
