from django.urls import path

from .views import QuerySeriesAPIView, QueryStudyAPIView

urlpatterns = [
    path(
        "<str:pacs>/qidors/studies/",
        QueryStudyAPIView.as_view(),
        name="qido_rs-studies",
    ),
    path(
        "<str:pacs>/qidors/series/",
        QuerySeriesAPIView.as_view(),
        name="qido_rs-series",
    ),
    path(
        "<str:pacs>/qidors/studies/<str:study_uid>/series/",
        QuerySeriesAPIView.as_view(),
        name="qido_rs-series_with_study_uid",
    ),
]
