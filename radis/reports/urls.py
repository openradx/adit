from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import ReportDetailView, ReportPreviewView

urlpatterns = [
    path("<str:document_id>/preview/", ReportPreviewView.as_view(), name="report_preview"),
    path("<str:document_id>/", ReportDetailView.as_view(), name="report_detail"),
]

urlpatterns = format_suffix_patterns(urlpatterns)
