from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.testing_helpers import add_permission
from django.contrib.auth.models import Group


def create_selective_transfer_group() -> Group:
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "selective_transfer", "add_selectivetransferjob")
    add_permission(group, "selective_transfer", "view_selectivetransferjob")
    return group
