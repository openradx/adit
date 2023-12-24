from django.urls import path

from radis.notes.views import NoteAvailableBadgeView, NoteEditView, NoteListView, NoteTextView

urlpatterns = [
    path("", NoteListView.as_view(), name="note_list"),
    path("text/<int:pk>/", NoteTextView.as_view(), name="note_text"),
    path("edit/<int:report_id>/", NoteEditView.as_view(), name="note_edit"),
    path(
        "available-badge/<int:report_id>/",
        NoteAvailableBadgeView.as_view(),
        name="note_available_badge",
    ),
]
