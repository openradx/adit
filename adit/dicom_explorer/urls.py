from django.urls import path

from .views import dicom_explorer_form_view, dicom_explorer_resources_view

# See DICOMweb RESTful resources
# https://www.dicomstandard.org/dicomweb/restful-structure/

urlpatterns = [
    path(
        "",
        dicom_explorer_form_view,
        name="dicom_explorer_form",
    ),
    path(
        "servers/",
        dicom_explorer_resources_view,
        name="dicom_explorer_server_query",
    ),
    path(
        "servers/<server_id>/",
        dicom_explorer_resources_view,
        name="dicom_explorer_server_detail",
    ),
    path(
        "servers/<server_id>/patients/",
        dicom_explorer_resources_view,
        name="dicom_explorer_patient_query",
    ),
    path(
        "servers/<server_id>/patients/<patient_id>/",
        dicom_explorer_resources_view,
        name="dicom_explorer_patient_detail",
    ),
    path(
        "servers/<server_id>/studies/",
        dicom_explorer_resources_view,
        name="dicom_explorer_study_query",
    ),
    path(
        "servers/<server_id>/studies/<study_uid>/",
        dicom_explorer_resources_view,
        name="dicom_explorer_study_detail",
    ),
    path(
        "servers/<server_id>/studies/<study_uid>/series/",
        dicom_explorer_resources_view,
        name="dicom_explorer_series_query",
    ),
    path(
        "servers/<server_id>/studies/<study_uid>/series/<series_uid>/",
        dicom_explorer_resources_view,
        name="dicom_explorer_series_detail",
    ),
]
