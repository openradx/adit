from django.urls import path

from .views import RetrieveSeriesAPIView, RetrieveStudyAPIView

urlpatterns = [
    path(
        "<str:pacs>/wadors/studies/",
        RetrieveStudyAPIView.as_view(),
        name="wado_rs-studies",
    ),
    path(
        "<str:pacs>/wadors/studies/<str:StudyInstanceUID>/",
        RetrieveStudyAPIView.as_view(),
        name="wado_rs-studies_with_id",
    ),
    path(
        "<str:pacs>/wadors/studies/<str:StudyInstanceUID>/<str:mode>/",
        RetrieveStudyAPIView.as_view(),
        name="wado_rs-studies_with_id_and_mode",
    ),
    path(
        "<str:pacs>/wadors/series/",
        RetrieveSeriesAPIView.as_view(),
        name="wado_rs-series",
    ),
    path(
        "<str:pacs>/wadors/studies/<str:StudyInstanceUID>/series/<str:SeriesInstanceUID>/",
        RetrieveSeriesAPIView.as_view(),
        name="wado_rs-series_with_id",
    ),
]
