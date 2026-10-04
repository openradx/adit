from adit.core.tables import TransferJobTable

from .models import RouterJob


class RouterJobTable(TransferJobTable):
    class Meta(TransferJobTable.Meta):
        model = RouterJob
        fields = ("id", "rule", "status", "message", "created")
        empty_text = "No router jobs to show"
