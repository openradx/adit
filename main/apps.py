from django.apps import AppConfig
from django.db.models.signals import post_migrate

class MainConfig(AppConfig):
    name = 'main'

    def ready(self):
        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)

def init_db(sender, **kwargs):
    create_site_config()

def create_site_config():
    from .models import SiteConfig
    config = SiteConfig.objects.first()
    if not config:
        SiteConfig.objects.create()