from django.apps import AppConfig
from main.registries import nav_menu_items


class BatchConfig(AppConfig):
    name = 'batch'

    def ready(self):
        nav_menu_items.append({
            "name": "new_batch_transfer",
            "label": "Batch Transfer",
            "url": "/batch/new/"
        })
