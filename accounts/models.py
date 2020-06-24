from django.db import models
from django.contrib.auth.models import AbstractUser

class Department(models.Model):
    name = models.CharField(max_length=128)
    institution = models.CharField(max_length=128)

class User(AbstractUser):
    phone_number = models.CharField(max_length=64)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)