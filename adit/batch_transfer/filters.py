import django_filters
from .models import BatchTransferRequest


class BatchTransferRequestFilter(django_filters.FilterSet):
    class Meta:
        model = BatchTransferRequest
        fields = ("status",)
