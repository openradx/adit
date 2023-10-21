from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.detail import DetailView

from .models import Report


class ReportDetailView(LoginRequiredMixin, DetailView):
    model = Report
    template_name = "reports/report_detail.html"
    context_object_name = "report"
    slug_url_kwarg = "document_id"
    slug_field = "document_id"


class ReportPreviewView(ReportDetailView):
    template_name = "reports/report_preview.html"
