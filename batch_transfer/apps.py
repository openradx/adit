from django.apps import AppConfig
from django.db.models.signals import post_migrate
from main.site import register_main_menu_item, register_dicom_job

class BatchTransferConfig(AppConfig):
    name = 'batch_transfer'

    def ready(self):
        register_app()

        # Put calls to db stuff in this signal handler
        post_migrate.connect(init_db, sender=self)

def register_app():
    register_main_menu_item(
        url_name='new_batch_transfer_job',
        label='Batch Transfer'
    )
    
    from .models import BatchTransferJob
    from .views import BatchTransferJobDetail
    register_dicom_job(
        type_key=BatchTransferJob.JOB_TYPE,
        type_name='Batch transfer job',
        detail_view=BatchTransferJobDetail
    )

def init_db(sender, **kwargs):
    create_group()
    create_site_config()

def create_group():
    from accounts.utils import create_group_with_permissions
    create_group_with_permissions(
        'batch_transferrers',
        (
            'batch_transfer.add_batchtransferjob',
            'batch_transfer.view_batchtransferjob',
            'batch_transfer.can_cancel_batchtransferjob'
        )
    )

def create_site_config():
    from .models import SiteConfig
    config = SiteConfig.objects.first()
    if not config:
        SiteConfig.objects.create()