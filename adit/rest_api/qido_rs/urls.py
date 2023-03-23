from django.urls import path
from .views import QuerySeriesAPIView, QueryStudyAPIView

urlpatterns = [
    path(
        "<str:pacs>/qidors/studies/",
        QueryStudyAPIView.as_view(),
        name="qido_rs-studies",
    ),
    path(
        "<str:pacs>/qidors/studies/<str:StudyInstanceUID>/",
        QueryStudyAPIView.as_view(),
        name="qido_rs-studies_with_id",
    ),
    path(
        "<str:pacs>/qidors/studies/<str:StudyInstanceUID>/series/",
        QuerySeriesAPIView.as_view(),
        name="qido_rs-series",
    ),
    path(
        "<str:pacs>/quidors/studies/<str:StudyInstanceUID>/series/<str:SeriesInstanceUID>/",
        QuerySeriesAPIView.as_view(),
        name="qido_rs-series-with_id",
    ),
]
