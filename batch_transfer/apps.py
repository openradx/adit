from django.apps import AppConfig
from main.registries import nav_menu_items


class BatchTransferConfig(AppConfig):
    name = 'batch_transfer'

    def ready(self):
        nav_menu_items.append({
            "name": "new_batch_transfer",
            "label": "Batch Transfer",
            "url": "/batch-transfer/new/"
        })
