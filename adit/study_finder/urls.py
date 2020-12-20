from django.urls import path
from .views import (
    StudyFinderJobListView,
    StudyFinderJobCreateView,
    StudyFinderJobDetailView,
    StudyFinderJobDeleteView,
    StudyFinderJobCancelView,
    StudyFinderJobVerifyView,
    StudyFinderQueryDetailView,
    StudyFinderResultsDownloadView,
)


urlpatterns = [
    path(
        "jobs/",
        StudyFinderJobListView.as_view(),
        name="study_finder_job_list",
    ),
    path(
        "jobs/new/",
        StudyFinderJobCreateView.as_view(),
        name="study_finder_job_create",
    ),
    path(
        "jobs/<int:pk>/",
        StudyFinderJobDetailView.as_view(),
        name="study_finder_job_detail",
    ),
    path(
        "jobs/<int:pk>/delete/",
        StudyFinderJobDeleteView.as_view(),
        name="study_finder_job_delete",
    ),
    path(
        "jobs/<int:pk>/cancel/",
        StudyFinderJobCancelView.as_view(),
        name="study_finder_job_cancel",
    ),
    path(
        "jobs/<int:pk>/verify/",
        StudyFinderJobVerifyView.as_view(),
        name="study_finder_job_verify",
    ),
    path(
        "queries/<int:pk>/",
        StudyFinderQueryDetailView.as_view(),
        name="study_finder_query_detail",
    ),
    path(
        "jobs/<int:pk>/download",
        StudyFinderResultsDownloadView.as_view(),
        name="study_finder_results_download",
    ),
]
