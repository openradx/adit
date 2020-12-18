import django_filters
from adit.core.filters import DicomJobFilter
from adit.core.forms import SingleFilterFormHelper
from .models import BatchTransferJob, BatchTransferRequest


class BatchTransferJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = BatchTransferJob


class BatchTransferRequestFilter(django_filters.FilterSet):
    class Meta:
        model = BatchTransferRequest
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = SingleFilterFormHelper(self.request.GET, self.Meta.fields[0])
