from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import ReportDetailAPIView, ReportListAPIView

urlpatterns = [
    path("reports/", ReportListAPIView.as_view()),
    path("reports/<str:document_id>/", ReportDetailAPIView.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns)
