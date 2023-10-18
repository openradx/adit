from django.urls import path

from .views import (
    CollectedReportRemoveView,
    CollectionCountBadgeView,
    CollectionCreateView,
    CollectionDeleteView,
    CollectionDetailView,
    CollectionListView,
    CollectionSelectView,
    CollectionUpdateView,
)

urlpatterns = [
    path("", CollectionListView.as_view(), name="collection_list"),
    path("create/", CollectionCreateView.as_view(), name="collection_create"),
    path("update/<int:pk>/", CollectionUpdateView.as_view(), name="collection_update"),
    path("delete/<int:pk>/", CollectionDeleteView.as_view(), name="collection_delete"),
    path(
        "select/<str:document_id>/",
        CollectionSelectView.as_view(),
        name="collection_select",
    ),
    path(
        "count-badge/<str:document_id>/",
        CollectionCountBadgeView.as_view(),
        name="collection_count_badge",
    ),
    path("<int:pk>/", CollectionDetailView.as_view(), name="collection_detail"),
    path(
        "<int:collection_pk>/remove/<int:collected_report_pk>/",
        CollectedReportRemoveView.as_view(),
        name="collected_report_remove",
    ),
]
