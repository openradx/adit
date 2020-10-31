import django_filters
from adit.main.forms import MultiInlineFilterFormHelper
from .models import TransferJob


class TransferJobFilter(django_filters.FilterSet):
    class Meta:
        model = TransferJob
        fields = ("job_type", "status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = MultiInlineFilterFormHelper(
            self.request.GET, self.Meta.fields
        )
