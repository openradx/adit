from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns

from .views import ReportDetail, ReportList

urlpatterns = [
    path("reports/", ReportList.as_view()),
    path("reports/<str:pk>/", ReportDetail.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns)
