from rest_framework import viewsets
from rest_framework.serializers import BaseSerializer

from radis.reports.models import Report

from .serializers import ReportSerializer
from .site import report_event_handlers


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    queryset = Report.objects.all()

    def perform_create(self, serializer: BaseSerializer) -> None:
        super().perform_create(serializer)
        assert serializer.instance
        report: Report = serializer.instance
        for handler in report_event_handlers:
            handler("created", report)

    def perform_update(self, serializer: BaseSerializer) -> None:
        super().perform_update(serializer)
        assert serializer.instance
        report: Report = serializer.instance
        for handler in report_event_handlers:
            handler("updated", report)

    def perform_destroy(self, instance: Report) -> None:
        super().perform_destroy(instance)
        for handler in report_event_handlers:
            handler("deleted", instance)
