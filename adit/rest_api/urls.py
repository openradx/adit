from django.urls import path
from .views import TestView

urlpatterns = [
    path(
        "rest_test/",
        TestView.as_view(),
        name="rest_test",
    ),
]
