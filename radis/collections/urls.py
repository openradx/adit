from django.urls import path

from .views import ReportCollectionListView

urlpatterns = [
    path("", ReportCollectionListView.as_view(), name="collection_list"),
]
