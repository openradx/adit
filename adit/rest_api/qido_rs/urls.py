from django.urls import path
from .views import (
    QueryStudyAPIView,
    QuerySeriesAPIView,
)

urlpatterns = [
    path(
        "<str:pacs>/qidors/studies/",
        QueryStudyAPIView.as_view(),
    ),
    path(
        "<str:pacs>/qidors/studies/<str:StudyInstanceUID>/",
        QueryStudyAPIView.as_view(),
    ),
    path(
        "<str:pacs>/qidors/studies/<str:StudyInstanceUID>/series/",
        QuerySeriesAPIView.as_view(),
    ),
    path(
        "<str:pacs>/quidors/studies/<str:StudyInstanceUID>/series/<str:SeriesInstanceUID>/",
        QuerySeriesAPIView.as_view(),
    ),
]
