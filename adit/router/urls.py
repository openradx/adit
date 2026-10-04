from django.urls import path

from .views import RouterJobListView

urlpatterns = [
    path("jobs/", RouterJobListView.as_view(), name="router_job_list"),
]
