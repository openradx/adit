from django.urls import path

from .views import BatchTransferJobCreate

urlpatterns = [
    path('batch-transfer/', BatchTransferJobCreate.as_view(), name='batch_transfer_job_create')
]