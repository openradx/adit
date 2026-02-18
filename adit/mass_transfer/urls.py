from django.urls import path

from .views import (
    MassTransferFilterCreateView,
    MassTransferFilterDeleteView,
    MassTransferFilterListView,
    MassTransferFilterUpdateView,
    MassTransferJobCancelView,
    MassTransferJobCreateView,
    MassTransferJobDeleteView,
    MassTransferJobDetailView,
    MassTransferJobListView,
    MassTransferJobRestartView,
    MassTransferJobResumeView,
    MassTransferJobRetryView,
    MassTransferJobVerifyView,
    MassTransferTaskDeleteView,
    MassTransferTaskDetailView,
    MassTransferTaskKillView,
    MassTransferTaskResetView,
    MassTransferUpdatePreferencesView,
)

urlpatterns = [
    path("filters/", MassTransferFilterListView.as_view(), name="mass_transfer_filter_list"),
    path(
        "filters/new/",
        MassTransferFilterCreateView.as_view(),
        name="mass_transfer_filter_create",
    ),
    path(
        "filters/<int:pk>/edit/",
        MassTransferFilterUpdateView.as_view(),
        name="mass_transfer_filter_update",
    ),
    path(
        "filters/<int:pk>/delete/",
        MassTransferFilterDeleteView.as_view(),
        name="mass_transfer_filter_delete",
    ),
    path(
        "preferences/",
        MassTransferUpdatePreferencesView.as_view(),
        name="mass_transfer_update_preferences",
    ),
    path("jobs/", MassTransferJobListView.as_view(), name="mass_transfer_job_list"),
    path("jobs/new/", MassTransferJobCreateView.as_view(), name="mass_transfer_job_create"),
    path("jobs/<int:pk>/", MassTransferJobDetailView.as_view(), name="mass_transfer_job_detail"),
    path(
        "jobs/<int:pk>/delete/",
        MassTransferJobDeleteView.as_view(),
        name="mass_transfer_job_delete",
    ),
    path(
        "jobs/<int:pk>/verify/",
        MassTransferJobVerifyView.as_view(),
        name="mass_transfer_job_verify",
    ),
    path(
        "jobs/<int:pk>/cancel/",
        MassTransferJobCancelView.as_view(),
        name="mass_transfer_job_cancel",
    ),
    path(
        "jobs/<int:pk>/resume/",
        MassTransferJobResumeView.as_view(),
        name="mass_transfer_job_resume",
    ),
    path(
        "jobs/<int:pk>/retry/",
        MassTransferJobRetryView.as_view(),
        name="mass_transfer_job_retry",
    ),
    path(
        "jobs/<int:pk>/restart/",
        MassTransferJobRestartView.as_view(),
        name="mass_transfer_job_restart",
    ),
    path("tasks/<int:pk>/", MassTransferTaskDetailView.as_view(), name="mass_transfer_task_detail"),
    path(
        "tasks/<int:pk>/delete/",
        MassTransferTaskDeleteView.as_view(),
        name="mass_transfer_task_delete",
    ),
    path(
        "tasks/<int:pk>/reset/",
        MassTransferTaskResetView.as_view(),
        name="mass_transfer_task_reset",
    ),
    path(
        "tasks/<int:pk>/kill/",
        MassTransferTaskKillView.as_view(),
        name="mass_transfer_task_kill",
    ),
]
