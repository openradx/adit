import django_filters
from adit.core.filters import TransferJobFilter
from adit.core.forms import SingleFilterFormHelper
from .models import BatchTransferJob, BatchTransferRequest


class BatchTransferJobFilter(TransferJobFilter):
    class Meta(TransferJobFilter.Meta):
        model = BatchTransferJob


class BatchTransferRequestFilter(django_filters.FilterSet):
    class Meta:
        model = BatchTransferRequest
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = SingleFilterFormHelper(self.request.GET, self.Meta.fields[0])
