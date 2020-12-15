import django_filters
from adit.core.forms import MultiInlineFilterFormHelper, SingleFilterFormHelper
from .models import TransferTask


class TransferJobFilter(django_filters.FilterSet):
    class Meta:
        model = None
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = MultiInlineFilterFormHelper(
            self.request.GET, self.Meta.fields
        )


class TransferTaskFilter(django_filters.FilterSet):
    class Meta:
        model = TransferTask
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.helper = SingleFilterFormHelper(self.request.GET, self.Meta.fields[0])
