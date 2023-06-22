from django.urls import include, path

urlpatterns = [
    path("", include("adit.dicom_web.qidors.urls")),
    path("", include("adit.dicom_web.wadors.urls")),
]
