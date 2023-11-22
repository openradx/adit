from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractUser, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


class User(AbstractUser):
    id: int
    phone_number = models.CharField(max_length=64)
    department = models.CharField(max_length=128)
    preferences = models.JSONField(default=dict)

    if TYPE_CHECKING:
        institutes = RelatedManager["Institute"]()

    def is_group_member(self, group_name: str):
        return self.groups.filter(name=group_name).exists()

    def join_group(self, group_name: str):
        group = Group.objects.get(name=group_name)
        self.groups.add(group)

    def add_permission(self, permission_codename: str, model: models.Model | None = None):
        if model:
            content_type = ContentType.objects.get_for_model(model)
            permission = Permission.objects.get(
                codename=permission_codename, content_type=content_type
            )
            self.user_permissions.add(permission)
        else:
            permissions = Permission.objects.filter(codename=permission_codename)

            if len(permissions) == 0:
                raise ObjectDoesNotExist(f'Permission "{permission_codename}" does not exist.')

            self.user_permissions.add(*permissions)


class Institute(models.Model):
    id: int
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True, max_length=1024)
    users = models.ManyToManyField(User, related_name="institutes", blank=True)

    def __str__(self):
        return self.name
