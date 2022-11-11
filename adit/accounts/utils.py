import logging
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from .models import User

logger = logging.getLogger(__name__)


def _permission_names_to_objects(names):
    """
    Given an iterable of permission names (e.g. 'app_label.add_model'),
    return an iterable of Permission objects for them.  The permission
    must already exist, because a permission name is not enough information
    to create a new permission.
    """
    result = []
    for name in names:
        app_label, codename = name.split(".", 1)
        try:
            result.append(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )
        except Permission.DoesNotExist:
            logger.exception("NO SUCH PERMISSION: %s, %s", app_label, codename)
            raise
    return result


def create_group_with_permissions(group_name, permission_names):
    """Create a group with added permissions programmatically.

    Inspired by https://cheat.readthedocs.io/en/latest/django/permissions.html
    """
    group, created = Group.objects.get_or_create(name=group_name)
    if created:
        logger.info("Created group %s.", group_name)

    perms_to_add = _permission_names_to_objects(permission_names)
    group.permissions.add(*perms_to_add)
    if not created:
        # Group already existed - make sure it doesn't have any perms we didn't want
        perms_to_remove = set(group.permissions.all()) - set(perms_to_add)
        if perms_to_remove:
            group.permissions.remove(*perms_to_remove)


class UserPermissionManager:
    def __init__(self, user: User):
        self.user = user

    def add_group(self, group_name: str):
        group = Group.objects.get(name=group_name)
        self.user.groups.add(group)

    def add_permission(self, permission_name: str, model: models.Model = None):
        if model:
            content_type = ContentType.objects.get_for_model(model)
            permission = Permission.objects.get(codename=permission_name, content_type=content_type)
            self.user.user_permissions.add(permission)
        else:
            permissions = Permission.objects.filter(codename=permission_name)

            if len(permissions) == 0:
                raise ObjectDoesNotExist(f'Permission "{permission_name}" does not exist.')

            self.user.user_permissions.add(permissions)
