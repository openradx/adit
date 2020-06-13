from django.urls import path

from . import views

urlpatterns = [
    path('new/', views.new_batch_transfer, name='new_batch_transfer'),
]