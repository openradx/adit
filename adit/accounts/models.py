import logging

from django.contrib.auth.models import AbstractUser, Group
from django.db import models

logger = logging.getLogger(__name__)


class User(AbstractUser):
    id: int
    phone_number = models.CharField(max_length=64)
    department = models.CharField(max_length=128)
    preferences = models.JSONField(default=dict)
    active_group = models.ForeignKey(
        Group, on_delete=models.SET_NULL, null=True, related_name="active_users"
    )

    def save(self, *args, **kwargs):
        if self.active_group and self.active_group not in self.groups.all():
            logger.warn(
                f"Active group '{self.active_group.name}' not in user's groups. "
                "Setting active group to None."
            )
            self.active_group = None
        super().save(*args, **kwargs)

    def change_active_group(self, new_group):
        if new_group in self.groups.all():
            self.active_group = new_group
            self.save()
        else:
            raise ValueError("New group must be one of the user's groups")
