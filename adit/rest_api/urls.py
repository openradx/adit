from django.urls import path, include

urlpatterns = [
    path("", include("adit.rest_api.qido_rs.urls")),
    path("", include("adit.rest_api.wado_rs.urls"))
]
