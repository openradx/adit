import django_filters
from adit_radis_shared.common.forms import SingleFilterFieldFormHelper
from adit_radis_shared.common.types import with_form_helper
from django.http import HttpRequest

from adit.core.filters import DicomJobFilter, DicomTaskFilter

from .models import MassTransferJob, MassTransferTask, MassTransferVolume


class MassTransferJobFilter(DicomJobFilter):
    class Meta(DicomJobFilter.Meta):
        model = MassTransferJob


class MassTransferTaskFilter(DicomTaskFilter):
    class Meta(DicomTaskFilter.Meta):
        model = MassTransferTask


class MassTransferVolumeFilter(django_filters.FilterSet):
    request: HttpRequest

    class Meta:
        model = MassTransferVolume
        fields = ("status",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        with_form_helper(self.form).helper = SingleFilterFieldFormHelper(
            self.request.GET, "status"
        )
