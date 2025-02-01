from django.urls import path

from .views import (
    QuerySeriesAPIView,
    QueryStudiesAPIView,
    RetrieveSeriesAPIView,
    RetrieveSeriesMetadataAPIView,
    RetrieveStudyAPIView,
    RetrieveStudyMetadataAPIView,
    StoreImagesAPIView,
)

# For possible DICOMweb target resources see
# https://www.dicomstandard.org/using/dicomweb/restful-structure
#
# As we just act as a proxy we only implement the mandatory target resources, see
# https://dicom.nema.org/medical/dicom/current/output/html/part18.html#table_10.6.1-1
#
# As [DICOMweb client](https://github.com/ImagingDataCommons/dicomweb-client) does not use trailing
# slashes in URLs we also don't use them in the URL patterns (in contrast to DRF best practice).
#
# TODO: Implement remaining target resource URLs
urlpatterns = [
    path(
        "<str:ae_title>/qidors/studies",
        QueryStudiesAPIView.as_view(),
        name="qido_rs-studies",
    ),
    path(
        "<str:ae_title>/qidors/studies/<str:study_uid>/series",
        QuerySeriesAPIView.as_view(),
        name="qido_rs-series_with_study_uid",
    ),
    path(
        "<str:ae_title>/wadors/studies/<str:study_uid>",
        RetrieveStudyAPIView.as_view(),
        name="wado_rs-study_with_study_uid",
    ),
    path(
        "<str:ae_title>/wadors/studies/<str:study_uid>/metadata",
        RetrieveStudyMetadataAPIView.as_view(),
        name="wado_rs-study_metadata_with_study_uid",
    ),
    path(
        "<str:ae_title>/wadors/studies/<str:study_uid>/series/<str:series_uid>",
        RetrieveSeriesAPIView.as_view(),
        name="wado_rs-series_with_study_uid_and_series_uid",
    ),
    path(
        "<str:ae_title>/wadors/studies/<str:study_uid>/series/<str:series_uid>/metadata",
        RetrieveSeriesMetadataAPIView.as_view(),
        name="wado_rs-series_metadata_with_study_uid_and_series_uid",
    ),
    path(
        "<str:ae_title>/stowrs/studies",
        StoreImagesAPIView.as_view(),
        name="stow_rs-series",
    ),
    path(
        "<str:ae_title>/stowrs/studies/<str:study_uid>",
        StoreImagesAPIView.as_view(),
        name="stow_rs-series_with_study_uid",
    ),
]
