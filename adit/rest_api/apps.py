from django.apps import AppConfig
from django.db.models.signals import post_migrate


class RestApiConfig(AppConfig):
    name = "adit.rest_api"
