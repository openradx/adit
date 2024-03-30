# type: ignore

import pytest
from django_test_migrations.migrator import Migrator


@pytest.mark.django_db
def test_0007_convert_institutes_to_groups(migrator: Migrator):
    old_state = migrator.apply_initial_migration(("accounts", "0006_user_active_group"))

    User = old_state.apps.get_model("accounts", "User")
    Institute = old_state.apps.get_model("accounts", "Institute")

    user1 = User.objects.create(
        username="user1",
    )
    user2 = User.objects.create(
        username="user2",
    )
    institute = Institute.objects.create(
        name="Institute 1",
        description="Will unfortunately get lost",
    )
    institute.users.add(user1)
    institute.users.add(user2)

    new_state = migrator.apply_tested_migration(("accounts", "0007_convert_institutes_to_groups"))

    Group = new_state.apps.get_model("auth", "Group")
    group = Group.objects.first()

    assert Group.objects.count() == 1
    assert group.name == institute.name
    assert group.user_set.count() == 2
    assert group.user_set.filter(pk=user1.pk).exists()
    assert group.user_set.filter(pk=user2.pk).exists()
    for user in group.user_set.all():
        assert user.active_group == group
