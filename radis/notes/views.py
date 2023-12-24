from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import render
from django.views.generic import DetailView, UpdateView, View
from django_filters.views import FilterView
from django_htmx.http import HttpResponseClientRefresh, trigger_client_event

from radis.core.mixins import HtmxOnlyMixin, PageSizeSelectMixin
from radis.core.types import AuthenticatedHttpRequest
from radis.notes.filters import NoteFilter
from radis.notes.forms import NoteEditForm
from radis.notes.models import Note
from radis.reports.models import Report


class NoteListView(LoginRequiredMixin, PageSizeSelectMixin, FilterView):
    template_name = "notes/note_list.html"
    context_object_name = "notes"
    filterset_class = NoteFilter
    paginate_by = 10
    request: AuthenticatedHttpRequest

    def get_queryset(self) -> QuerySet[Note]:
        return Note.objects.filter(owner=self.request.user)


class NoteTextView(LoginRequiredMixin, HtmxOnlyMixin, DetailView):
    template_name = "notes/_note_text.html"
    request: AuthenticatedHttpRequest

    def get_queryset(self) -> QuerySet[Note]:
        return Note.objects.filter(owner=self.request.user)


class NoteEditView(LoginRequiredMixin, HtmxOnlyMixin, UpdateView):
    """A combined note create/update view to be presented in a dialog.

    Also deletes the note if the text is empty.
    """

    model = Note
    form_class = NoteEditForm
    template_name = "notes/_note_edit.html"
    reload_on_note_delete: bool
    request: AuthenticatedHttpRequest

    def get_object(self, queryset: QuerySet[Note] | None = None) -> Note | None:
        print("get object")
        reload_on_note_delete = self.request.GET.get("reload_on_note_delete")
        self.reload_on_note_delete = reload_on_note_delete == "yes"

        if queryset is None:
            queryset = self.get_queryset()

        report_id: int = self.kwargs["report_id"]
        return Note.objects.filter(report_id=report_id).first()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["report_id"] = self.kwargs["report_id"]
        context["reload_on_note_delete"] = self.reload_on_note_delete
        return context

    def form_valid(self, form: NoteEditForm) -> HttpResponse:
        report_id: int = self.kwargs["report_id"]

        note: Note = form.instance
        note.owner = self.request.user
        note.report_id = report_id

        text: str = note.text
        if note.id is not None and len(text.strip()) == 0:
            note.delete()
            print("delete")
            if self.reload_on_note_delete:
                print("reload")

                return HttpResponseClientRefresh()
        elif len(text.strip()) > 0:
            form.save()

        response = HttpResponse(status=204)
        response = trigger_client_event(response, f"noteChanged_{report_id}")
        return response


class NoteAvailableBadgeView(LoginRequiredMixin, HtmxOnlyMixin, View):
    def get(self, request: AuthenticatedHttpRequest, report_id: int) -> HttpResponse:
        report = Report.objects.get(id=report_id)

        return render(
            request,
            "notes/_note_available_badge.html",
            {"report": report},
        )
