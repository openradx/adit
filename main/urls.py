from django.urls import path
from django.views.generic import TemplateView
from .views import DicomJobListView

urlpatterns = [
    path('', TemplateView.as_view(template_name="main/home.html"), name='home'),
    path('jobs/', DicomJobListView.as_view(), name='dicom_job_list')
]