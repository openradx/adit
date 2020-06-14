from django.apps import AppConfig
from main.site import register_main_menu_item, register_transfer_job_type

BATCH_TRANSFER_JOB_KEY = 'BA'

class BatchTransferConfig(AppConfig):
    name = 'batch_transfer'

    def ready(self):
        register_main_menu_item(
            name='new_batch_transfer',
            label='Batch Transfer',
            url='/batch-transfer/new/'
        )
        
        register_transfer_job_type(BATCH_TRANSFER_JOB_KEY, 'Batch transfer job')
