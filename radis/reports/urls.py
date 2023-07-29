from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import ReportDetailView

urlpatterns = [
    path("<str:doc_id>/", ReportDetailView.as_view(), name="report_detail"),
]

urlpatterns = format_suffix_patterns(urlpatterns)
