from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    phone_number = models.CharField(max_length=64)
    department = models.CharField(max_length=128)
    misc_settings = models.JSONField(null=True, blank=True)
