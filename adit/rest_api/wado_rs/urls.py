from django.urls import path
from .views import(
    RetrieveStudyAPIView,
    RetrieveSeriesAPIView,
)

urlpatterns = [
    path(
        "<str:pacs>/wadors/studies/",
        RetrieveStudyAPIView.as_view(),
    ),
    path(
        "<str:pacs>/wadors/studies/<str:StudyInstanceUID>/",
        RetrieveStudyAPIView.as_view(),
    ),
    path(
        "<str:pacs>/wadors/studies/<str:StudyInstanceUID>/<str:mode>/",
        RetrieveStudyAPIView.as_view(),
    ),
    path(
        "<str:pacs>/wadors/series/",
        RetrieveSeriesAPIView.as_view(),
    ),
    path(
        "<str:pacs>/wadors/studies/<str:StudyInstanceUID>/series/<str:SeriesInstanceUID>/",
        RetrieveSeriesAPIView.as_view(),
    ),
]