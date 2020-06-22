from django.urls import path
from django.views.generic import TemplateView
from .views import DicomJobTableView, render_job_detail

urlpatterns = [
    path('', TemplateView.as_view(template_name="main/home.html"), name='home'),
    path('jobs/', DicomJobTableView.as_view(), name='dicom_job_list'),
    path('jobs/<int:pk>/', render_job_detail, name='dicom_job_detail')
]