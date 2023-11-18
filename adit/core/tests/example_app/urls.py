from django.urls import path

from .views import ExampleTransferJobCancelView

urlpatterns = [
    path(
        "jobs/<int:pk>/cancel/",
        ExampleTransferJobCancelView.as_view(),
        name="example_transfer_job_cancel",
    )
]
