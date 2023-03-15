from django.urls import include, path

from . import views

urlpatterns = [
    path("", include("registration.backends.admin_approval.urls")),
    path("<int:pk>/", views.UserProfileView.as_view(), name="user_profile"),
]
