from django.urls import path

from .views import (
    QuerySeriesAPIView,
    QueryStudyAPIView,
    RetrieveSeriesAPIView,
    RetrieveStudyAPIView,
    StoreAPIView,
)

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
    path(
        "<str:pacs>/wadors/studies/<str:study_uid>/",
        RetrieveStudyAPIView.as_view(),
        name="wado_rs-studies_with_study_uid",
    ),
    path(
        "<str:pacs>/wadors/studies/<str:study_uid>/<str:mode>/",
        RetrieveStudyAPIView.as_view(),
        name="wado_rs-studies_with_study_uid_and_mode",
    ),
    path(
        "<str:pacs>/wadors/studies/<str:study_uid>/series/<str:series_uid>/",
        RetrieveSeriesAPIView.as_view(),
        name="wado_rs-series_with_study_uid_and_series_uid",
    ),
    path(
        "<str:pacs>/wadors/studies/<str:study_uid>/series/<str:series_uid>/<str:mode>/",
        RetrieveSeriesAPIView.as_view(),
        name="wado_rs-series_with_study_uid_and_series_uid_and_mode",
    ),
    path(
        "<str:pacs>/stowrs/studies",
        StoreAPIView.as_view(),
        name="stow_rs-series",
    ),
    path(
        "<str:pacs>/stowrs/studies/<str:study_uid>",
        StoreAPIView.as_view(),
        name="stow_rs-series_with_study_uid",
    ),
]
