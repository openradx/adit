import django_filters
from adit.main.forms import SingleFilterFormHelper
from .models import BatchTransferRequest


class BatchTransferRequestFilter(django_filters.FilterSet):
    class Meta:
        model = BatchTransferRequest
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["status"].label = "Filter by status"
        self.form.helper = SingleFilterFormHelper(self.request.GET, "status")
