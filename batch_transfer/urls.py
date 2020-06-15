from django.urls import path

from .views import BatchTransferJobCreate

urlpatterns = [
    path('add/', BatchTransferJobCreate.as_view(), name='add_batch_transfer_job'),
]