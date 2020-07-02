from django.apps import AppConfig


class MainConfig(AppConfig):
    name = 'main'

    def ready(self):
        create_site_config()

def create_site_config():
    from .models import SiteConfig
    SiteConfig.objects.get_or_create(id=1)