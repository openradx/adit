from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('', TemplateView.as_view(template_name="main/home.html"), name='home'),
    path('jobs/', views.TransferJobList.as_view(), name='transfer-job-list')
]