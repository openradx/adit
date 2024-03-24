from django.urls import include, path

from . import views

urlpatterns = [
    path("", include("registration.backends.admin_approval.urls")),
    path("profile/", views.UserProfileView.as_view(), name="profile"),
    path(
        "active-group/",
        views.ActiveGroupView.as_view(),
        name="active_group",
    ),
]
