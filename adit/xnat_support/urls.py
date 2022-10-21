from django.urls import path
from .views import CheckXnatSourceView
from .views import FindXnatProjectsView

urlpatterns = [
    path("check-xnat-src/<str:name>/", CheckXnatSourceView.as_view()),
    path("check-xnat-src/", CheckXnatSourceView.as_view()),
    path("find-xnat-projects/<str:name>/", FindXnatProjectsView.as_view()),
    path("find-xnat-projects/", FindXnatProjectsView.as_view()),
]
