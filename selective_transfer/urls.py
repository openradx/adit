from django.urls import path

from .views import QueryStudiesView

urlpatterns = [
    path('selective-transfer/', QueryStudiesView.as_view(), name='query_studies')
]