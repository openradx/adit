from django.apps import AppConfig
from main.site import register_main_menu_item, register_dicom_job

BATCH_TRANSFER_JOB_KEY = 'BA'

class BatchTransferConfig(AppConfig):
    name = 'batch_transfer'

    def ready(self):
        register_main_menu_item(
            url_name='new_batch_transfer_job',
            label='Batch Transfer'
        )
        
        from .views import BatchTransferJobDetail
        register_dicom_job(
            type_key=BATCH_TRANSFER_JOB_KEY,
            type_name='Batch transfer job',
            detail_view=BatchTransferJobDetail
        )
