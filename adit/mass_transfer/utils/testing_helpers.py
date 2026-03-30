from adit_radis_shared.accounts.factories import GroupFactory
from adit_radis_shared.common.utils.testing_helpers import add_permission


def create_mass_transfer_group():
    group = GroupFactory.create(name="Radiologists")
    add_permission(group, "mass_transfer", "add_masstransferjob")
    add_permission(group, "mass_transfer", "view_masstransferjob")
    return group
