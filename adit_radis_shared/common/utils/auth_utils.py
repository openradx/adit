from typing import TypeGuard

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models

from adit_radis_shared.accounts.models import User


def is_logged_in_user(user: AbstractBaseUser | AnonymousUser) -> TypeGuard[User]:
    return user.is_authenticated


def add_permission(
    user_or_group: User | Group,
    model_or_app_label: str | type[models.Model],
    codename: str,
):
    if isinstance(model_or_app_label, str):
        permission = Permission.objects.get(
            content_type__app_label=model_or_app_label, codename=codename
        )
    else:
        content_type = ContentType.objects.get_for_model(model_or_app_label)
        permission = Permission.objects.get(content_type=content_type, codename=codename)
    if isinstance(user_or_group, User):
        user_or_group.user_permissions.add(permission)
    else:
        user_or_group.permissions.add(permission)


def add_user_to_group(user: User, group: Group):
    user.groups.add(group)
    if not user.active_group:
        user.change_active_group(group)
