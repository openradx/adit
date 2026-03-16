import django_tables2 as tables
from django.utils.html import format_html

from adit.core.tables import DicomTaskTable, TransferJobTable

from .models import MassTransferJob, MassTransferTask, MassTransferVolume
from .templatetags.mass_transfer_extras import volume_status_css_class


class MassTransferJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):
        model = MassTransferJob


class MassTransferTaskTable(DicomTaskTable):
    class Meta(DicomTaskTable.Meta):
        model = MassTransferTask


class MassTransferVolumeTable(tables.Table):
    status = tables.Column(verbose_name="Status")
    study_info = tables.Column(verbose_name="Study Info", empty_values=(), orderable=False)
    modality = tables.Column(verbose_name="Modality")
    series_number = tables.Column(verbose_name="Series #")
    series_description = tables.Column(verbose_name="Series Description")
    institution_name = tables.Column(verbose_name="Institution")
    number_of_images = tables.Column(verbose_name="# Images")
    log = tables.Column(verbose_name="Reason", attrs={"td": {"class": "small"}})

    class Meta:
        model = MassTransferVolume
        fields = (
            "status",
            "study_info",
            "modality",
            "series_number",
            "series_description",
            "institution_name",
            "number_of_images",
            "log",
        )
        order_by = ("status", "study_datetime")
        empty_text = "No volumes to show"
        attrs = {"class": "table table-bordered table-hover table-sm"}

    def render_status(self, value, record):
        css_class = volume_status_css_class(record.status)
        return format_html(
            '<span class="{} text-nowrap">{}</span>', css_class, record.get_status_display()
        )

    def render_study_info(self, record):
        desc = record.study_description or "—"
        dt = record.study_datetime.strftime("%Y-%m-%d") if record.study_datetime else ""
        return format_html("{}<br><small class='text-muted'>{}</small>", desc, dt)

    def render_series_number(self, value):
        return value if value is not None else "—"

    def render_series_description(self, value):
        return value or "—"

    def render_log(self, value):
        return value or "—"
