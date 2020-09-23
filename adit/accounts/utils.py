import logging
from django.contrib.auth.models import Group, Permission

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
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
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
