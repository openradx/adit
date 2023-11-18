from django.urls import path

from .views import ExampleTransferJobCancelView, ExampleTransferJobDeleteView

urlpatterns = [
    path(
        "jobs/<int:pk>/delete/",
        ExampleTransferJobDeleteView.as_view(),
        name="example_transfer_job_delete",
    ),
    path(
        "jobs/<int:pk>/cancel/",
        ExampleTransferJobCancelView.as_view(),
        name="example_transfer_job_cancel",
    ),
]
