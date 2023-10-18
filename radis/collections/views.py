from typing import Any, cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import SuspiciousFileOperation, SuspiciousOperation
from django.db import IntegrityError
from django.db.models import Count, Exists, OuterRef, QuerySet
from django.forms import BaseModelForm
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView, View
from django.views.generic.detail import SingleObjectMixin
from django_filters.views import FilterView
from django_htmx.http import HttpResponseClientRefresh, trigger_client_event
from django_tables2 import SingleTableMixin

from radis.core.mixins import PageSizeSelectMixin
from radis.core.types import AuthenticatedHttpRequest

from .filters import CollectionFilter
from .forms import CollectionForm
from .models import CollectedReport, Collection
from .tables import CollectionTable


class CollectionListView(LoginRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView):
    request: AuthenticatedHttpRequest
    model = Collection
    table_class = CollectionTable
    filterset_class = CollectionFilter

    def get_template_names(self) -> list[str]:
        if self.request.htmx:
            return ["collections/_collection_list.html"]
        return ["collections/collection_list.html"]

    def get_queryset(self) -> QuerySet[Collection]:
        return (
            Collection.objects.filter(owner=self.request.user)
            .prefetch_related("reports")
            .annotate(num_reports=Count("reports"))
        )


class CollectionCreateView(
    LoginRequiredMixin,
    CreateView,
):
    model = Collection
    template_name = "collections/_collection_create.html"
    form_class = CollectionForm

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        form.instance.owner = self.request.user
        try:
            self.object = form.save()
        except IntegrityError as err:
            if "unique_collection_name_per_user" in str(err):
                form.add_error("name", "A collection with this name already exists.")
                return self.form_invalid(form)
            raise err

        response = HttpResponse(status=204)
        return trigger_client_event(response, "collectionListChanged")


class CollectionUpdateView(LoginRequiredMixin, UpdateView):
    model = Collection
    template_name = "collections/_collection_update.html"
    form_class = CollectionForm

    def get_queryset(self) -> QuerySet[Collection]:
        return super().get_queryset().filter(owner=self.request.user)

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        form.instance.owner = self.request.user
        try:
            self.object = form.save()
        except IntegrityError as err:
            if "unique_collection_name_per_user" in str(err):
                form.add_error("name", "A collection with this name already exists.")
                return self.form_invalid(form)
            raise err

        return HttpResponseClientRefresh()


class CollectionDeleteView(LoginRequiredMixin, SuccessMessageMixin, DeleteView):
    model = Collection
    success_url = reverse_lazy("collection_list")
    success_message = "Collection successfully deleted"

    def get_queryset(self) -> QuerySet[Collection]:
        return super().get_queryset().filter(owner=self.request.user)


class CollectionDetailView(
    LoginRequiredMixin,
    PageSizeSelectMixin,
    SingleObjectMixin,
    ListView,
):
    template_name = "collections/collection_detail.html"

    def get(self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object(queryset=Collection.objects.filter(owner=self.request.user))
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[CollectedReport]:
        return cast(Collection, self.object).reports.all()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["collection"] = context["object"]
        context["reports"] = context["object_list"]
        return context


class CollectionSelectView(LoginRequiredMixin, View):
    def get(self, request: AuthenticatedHttpRequest, document_id: str) -> HttpResponse:
        user_id = request.user.id
        collections = (
            Collection.objects.filter(owner_id=user_id)
            .order_by("name")
            .annotate(
                has_report=Exists(
                    CollectedReport.objects.filter(
                        collection_id=OuterRef("id"), document_id=document_id
                    )
                )
            )
            .all()
        )

        last_used_collection = Collection.objects.get_last_used_collection(owner_id=user_id)

        addable_collections: list[Collection] = []
        removable_collections: list[Collection] = []
        for collection in collections:
            if collection.has_report:
                removable_collections.append(collection)
            else:
                addable_collections.append(collection)

        return render(
            request,
            "collections/_collection_select.html",
            {
                "document_id": document_id,
                "addable_collections": addable_collections,
                "removable_collections": removable_collections,
                "last_used_collection": last_used_collection,
            },
        )

    def post(self, request: AuthenticatedHttpRequest, document_id: str) -> HttpResponse:
        user_id = request.user.id
        action = request.POST.get("action")
        collection_id = request.POST.get("collection")

        collection = Collection.objects.get(id=collection_id)
        if not collection or not collection.owner_id == user_id:
            raise SuspiciousFileOperation()

        response = HttpResponse(status=200)
        if action == "add":
            CollectedReport.objects.create(document_id=document_id, collection=collection)
            response = trigger_client_event(response, f"collectionsOfReportChanged_{document_id}")
        elif action == "remove":
            CollectedReport.objects.get(
                document_id=document_id, collection_id=collection_id
            ).delete()
            response = trigger_client_event(response, f"collectionsOfReportChanged_{document_id}")
        else:
            raise SuspiciousOperation(f"Invalid action: {action}")

        return response


class CollectionCountBadgeView(LoginRequiredMixin, View):
    def get(self, request: AuthenticatedHttpRequest, document_id: str) -> HttpResponse:
        owner_id = request.user.id
        collection_counts = CollectedReport.objects.get_collection_counts(owner_id, [document_id])
        collection_count = collection_counts[document_id]
        return render(
            request,
            "collections/_collection_count_badge.html",
            {"document_id": document_id, "collection_count": collection_count},
        )


class CollectedReportRemoveView(LoginRequiredMixin, View):
    def post(
        self, request: AuthenticatedHttpRequest, collection_pk: int, collected_report_pk: int
    ) -> HttpResponse:
        collection: Collection = get_object_or_404(
            Collection.objects.filter(owner=request.user), pk=collection_pk
        )
        collected_report: CollectedReport = get_object_or_404(
            collection.reports, pk=collected_report_pk
        )
        collected_report.delete()
        return HttpResponseClientRefresh()
