from django.urls import path

from .views import dicom_explorer_view

urlpatterns = [
    path(
        "dicom-explorer/",
        dicom_explorer_view,
        name="dicom_explorer",
    ),
]
