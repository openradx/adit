from django.urls import path
from django.views.generic import TemplateView
from .views import DicomJobTable, render_job_detail

urlpatterns = [
    path('', TemplateView.as_view(template_name="main/home.html"), name='home'),
    path('jobs/', DicomJobTable.as_view(), name='dicom_job_list'),
    path('jobs/<int:pk>/', render_job_detail, name='dicom_job_detail')
]