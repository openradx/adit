from django.urls import path

from .views import BatchTransferJobCreate, BatchTransferJobDetail

urlpatterns = [
    path('new/', BatchTransferJobCreate.as_view(), name='new_batch_transfer_job'),
    path('<int:pk>/', BatchTransferJobDetail.as_view(), name='batch_transfer_job_detail'),
]