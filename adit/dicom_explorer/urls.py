from django.urls import path, re_path

from .views import dicom_explorer_form_view, dicom_explorer_query_view

urlpatterns = [
    path("", dicom_explorer_form_view, name="dicom_explorer_form"),
    re_path(
        r"servers/((?P<server_id>\d+)/)?$",
        dicom_explorer_query_view,
        name="dicom_explorer_query_servers",
    ),
    re_path(
        r"servers/(?P<server_id>\d+)/patients/(?:(?P<patient_id>\d+)/)?$",
        dicom_explorer_query_view,
        name="dicom_explorer_query_patients",
    ),
    re_path(
        r"servers/(?P<server_id>\d+)/studies/(?:(?P<study_uid>\d+)/)?$",
        dicom_explorer_query_view,
        name="dicom_explorer_query_studies",
    ),
    re_path(
        r"servers/(?P<server_id>\d+)/studies/(?P<study_uid>\d+)/series/(?:(?P<series_uid>\d+)/)?$",
        dicom_explorer_query_view,
        name="dicom_explorer_query_series",
    ),
]
