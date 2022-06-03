from django.urls import path
from .views import SelectiveTransferJobListAPIView, TestView, SelectiveTransferJobDetailAPIView, QueryAPIView

urlpatterns = [
    path(
        "selective-transfer-jobs/",
        SelectiveTransferJobListAPIView.as_view(),
    ),
    path(
        "selective-transfer-jobs/<int:id>/",
        SelectiveTransferJobDetailAPIView.as_view(),
    ),
    path(
        "test/",
        TestView.as_view(),
    ),
    path(
        "query/<str:pacs>/studies/",
        QueryAPIView.as_view(),
    ),
    path(
        "query/<str:pacs>/series/",
        QueryAPIView.as_view(),
    ),
    path(
        "query/<str:pacs>/studies/<str:StudyInstanceUID>/series/",
        QueryAPIView.as_view(),
    ),
]
