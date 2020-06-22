from django.urls import path
from django.views.generic import TemplateView
from .views import DicomJobTableView

urlpatterns = [
    path('', TemplateView.as_view(template_name="main/home.html"), name='home'),
    path('jobs/', DicomJobTableView.as_view(), name='dicom_job_list')
]