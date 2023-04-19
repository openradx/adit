from django.apps import AppConfig
from django.db.models.signals import post_migrate
from adit.core.site import register_job_stats_collector, register_main_menu_item


class UploadConfig(AppConfig):

    name = "adit.upload"

    def ready(self):
        register_app()

def register_app():
    register_main_menu_item(
        url_name="upload_job_create",
        label="Upload",
    )

    #register_job_stats_collector(collect_job_stats)
