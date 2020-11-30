from django.urls import path

from .views import DicomExplorerView

urlpatterns = [
    path(
        "dicom-explorer/",
        DicomExplorerView.as_view(),
        name="dicom_explorer",
    ),
]
