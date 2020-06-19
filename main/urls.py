from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('jobs/', views.TransferJobList.as_view(), name='transfer-job-list')
]