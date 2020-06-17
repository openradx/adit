from django.urls import path

from .views import BatchTransferJobCreate, BatchTransferJobDetail

urlpatterns = [
    path('add/', BatchTransferJobCreate.as_view(), name='add-batch-transfer-job'),
    path('<int:pk>/', BatchTransferJobDetail.as_view(), name='batch-transfer-job-detail'),
]