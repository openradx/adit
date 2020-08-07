from django.urls import path
from django.views.generic import TemplateView
from .views import (
    DicomJobListView,
    render_job_detail,
    DicomJobDelete,
    DicomJobCancel,
    FlowerProxyView,
)

urlpatterns = [
    path("", TemplateView.as_view(template_name="main/home.html"), name="home"),
    path("jobs/", DicomJobListView.as_view(), name="dicom_job_list"),
    path("jobs/<int:pk>/", render_job_detail, name="dicom_job_detail"),
    path("jobs/<int:pk>/delete", DicomJobDelete.as_view(), name="dicom_job_delete"),
    path("jobs/<int:pk>/cancel", DicomJobCancel.as_view(), name="dicom_job_cancel"),
    FlowerProxyView.as_url(),
]
