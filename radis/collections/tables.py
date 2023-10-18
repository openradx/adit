import django_tables2 as tables
from django_tables2.utils import A

from .models import Collection


class CollectionTable(tables.Table):
    name = tables.LinkColumn("collection_detail", args=[A("pk")], attrs={"td": {"class": "w-100"}})
    created = tables.Column(attrs={"td": {"class": "text-nowrap text-end"}})
    num_reports = tables.Column(
        verbose_name="# Reports",
        attrs={
            "th": {"class": "text-nowrap"},
            "td": {"class": "text-center"},
        },
    )

    class Meta:
        model = Collection
        fields = ("name", "num_reports", "created")
        order_by = ("name",)
        empty_text = "No collections yet"
        attrs = {
            "class": "table table-bordered table-hover",
        }
