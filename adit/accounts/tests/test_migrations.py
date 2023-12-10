# type: ignore

import pytest
from django_test_migrations.migrator import Migrator


@pytest.mark.django_db
def test_0007_copy_user_profile(migrator: Migrator):
    old_state = migrator.apply_initial_migration(("accounts", "0006_user_profile"))

    User = old_state.apps.get_model("accounts", "User")
    user = User.objects.create(
        username="john_doe",
        email="some_secret",
        first_name="John",
        last_name="Doe",
        phone_number="123456789",
        department="Department of Radiology",
        preferences={"foo": "Bar"},
    )

    new_state = migrator.apply_tested_migration(("accounts", "0007_copy_user_profile"))
    UserProfile = new_state.apps.get_model("accounts", "UserProfile")

    profile = UserProfile.objects.get(user=user)

    assert profile.phone_number == user.phone_number
    assert profile.department == user.department
    assert profile.preferences == user.preferences
