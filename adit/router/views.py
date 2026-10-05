import json
from typing import Any, cast

from adit_radis_shared.common.mixins import PageSizeSelectMixin, RelatedFilterMixin
from adit_radis_shared.common.types import AuthenticatedHttpRequest
from adit_radis_shared.common.views import HtmxTemplateView
from django.contrib import messages
from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.defaultfilters import pluralize
from django.views.generic import DetailView, View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import CreateView, UpdateView
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin, SingleTableView

from adit.core.views import (
    DicomJobCancelView,
    DicomJobDetailView,
    DicomJobRestartView,
    DicomJobRetryView,
    DicomTaskDetailView,
    DicomTaskKillView,
    DicomTaskResetView,
)

from .filters import RouterJobFilter, RouterTaskFilter, RoutingRuleJobFilter
from .forms import RoutingRuleForm
from .mixins import RouterStaffRequiredMixin
from .models import RouterJob, RouterTask, RoutingRule
from .tables import (
    RouterJobTable,
    RouterTaskTable,
    RoutingRuleJobTable,
    RoutingRuleTable,
    with_deliveries,
)


class RouterJobListView(
    RouterStaffRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView
):
    model = RouterJob
    table_class = RouterJobTable
    filterset_class = RouterJobFilter
    template_name = "router/router_job_list.html"

    def get_queryset(self) -> QuerySet[RouterJob]:
        # Staff see every router job, so the Admin Section's ?all=1 changes nothing here.
        return RouterJob.objects.select_related("rule").order_by("-created")


class RoutingRuleListView(RouterStaffRequiredMixin, SingleTableView):
    model = RoutingRule
    table_class = RoutingRuleTable
    template_name = "router/routing_rule_list.html"

    def get_queryset(self) -> QuerySet[RoutingRule]:
        return with_deliveries(RoutingRule.objects.select_related("destination"))


class RoutingRuleDetailView(
    RouterStaffRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    model = RoutingRule
    context_object_name = "rule"
    template_name = "router/routing_rule_detail.html"
    table_class = RoutingRuleJobTable
    filterset_class = RoutingRuleJobFilter
    object: RoutingRule

    def get_queryset(self) -> QuerySet[RoutingRule]:
        return RoutingRule.objects.select_related("destination", "created_by")

    def get_filter_queryset(self) -> QuerySet[RouterJob]:
        return (
            self.object.jobs.select_related("batch")
            .prefetch_related("tasks")
            .order_by("-batch__closed_at", "-pk")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["filters_json"] = json.dumps(self.object.filters_json, indent=2)
        context["failed_count"] = self.object.jobs.filter(
            status=RouterJob.Status.FAILURE, batch__files_deleted_at__isnull=True
        ).count()
        return context


class RoutingRuleToggleView(RouterStaffRequiredMixin, SingleObjectMixin, View):
    model = RoutingRule

    def post(self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        rule = cast(RoutingRule, self.get_object())
        posted = request.POST.get("enabled")
        if posted not in ("0", "1"):
            raise SuspiciousOperation(f"Routing rule {rule.pk} can't be set to enabled={posted!r}.")
        enable = posted == "1"
        state = "enabled" if enable else "disabled"
        # The page posts the state its button shows, so a stale page can't flip a rule back.
        if rule.enabled == enable:
            messages.info(request, f'Routing rule "{rule.name}" is already {state}.')
            return redirect(rule)

        # Only enabling validates: a rule must stay easy to switch off, even one that no
        # longer validates, for example after its destination lost C-STORE support.
        if enable:
            try:
                rule.full_clean()
            except ValidationError as err:
                problems = " ".join(err.messages)
                messages.error(
                    request, f"The rule can't be enabled: {problems} Edit the rule first."
                )
                return redirect(rule)

        rule.enabled = enable
        rule.save(update_fields=["enabled", "updated"])
        messages.success(request, f'Routing rule "{rule.name}" is now {state}.')
        return redirect(rule)


class RoutingRuleRetryFailedView(RouterStaffRequiredMixin, SingleObjectMixin, View):
    model = RoutingRule

    def post(self, request: AuthenticatedHttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        rule = cast(RoutingRule, self.get_object())
        retried, not_retriable = rule.retry_failed_deliveries()
        studies = "that study" if not_retriable == 1 else "those studies"
        images_deleted = (
            "because the images were deleted from the spool; "
            f"have the PACS forward {studies} again."
        )
        if retried:
            message = f"{retried} failed deliver{pluralize(retried, 'y,ies')} will be retried."
            if not_retriable:
                message += f" {not_retriable} more could not be retried {images_deleted}"
            messages.success(request, message)
        elif not_retriable:
            messages.warning(request, f"No failed delivery could be retried {images_deleted}")
        else:
            messages.info(request, "This rule has no failed deliveries.")
        return redirect(rule)


class RouterJobDetailView(RouterStaffRequiredMixin, DicomJobDetailView):
    table_class = RouterTaskTable
    filterset_class = RouterTaskFilter
    model = RouterJob
    context_object_name = "job"
    template_name = "router/router_job_detail.html"

    def get_queryset(self) -> QuerySet[RouterJob]:
        return RouterJob.objects.select_related("rule", "owner", "batch__sender__server")


class RouterJobCancelView(RouterStaffRequiredMixin, DicomJobCancelView):
    model = RouterJob


class RouterJobRetryView(RouterStaffRequiredMixin, DicomJobRetryView):
    model = RouterJob


class RouterJobRestartView(RouterStaffRequiredMixin, DicomJobRestartView):
    model = RouterJob


class RouterTaskDetailView(RouterStaffRequiredMixin, DicomTaskDetailView):
    model = RouterTask
    job_url_name = "router_job_detail"
    template_name = "router/router_task_detail.html"


class RouterTaskResetView(RouterStaffRequiredMixin, DicomTaskResetView):
    model = RouterTask


class RouterTaskKillView(RouterStaffRequiredMixin, DicomTaskKillView):
    model = RouterTask


class RoutingRuleCreateView(RouterStaffRequiredMixin, CreateView):
    model = RoutingRule
    form_class = RoutingRuleForm
    template_name = "router/routing_rule_form.html"
    extra_context = {"page_title": "New Routing Rule"}

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form: RoutingRuleForm) -> HttpResponse:
        form.instance.created_by = self.request.user
        messages.success(self.request, f'Routing rule "{form.instance.name}" was created.')
        return super().form_valid(form)


class RoutingRuleUpdateView(RouterStaffRequiredMixin, UpdateView):
    model = RoutingRule
    form_class = RoutingRuleForm
    template_name = "router/routing_rule_form.html"
    extra_context = {"page_title": "Edit Routing Rule"}

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form: RoutingRuleForm) -> HttpResponse:
        messages.success(self.request, f'Routing rule "{form.instance.name}" was saved.')
        return super().form_valid(form)


class RouterHelpView(RouterStaffRequiredMixin, HtmxTemplateView):
    template_name = "router/_routing_rule_help.html"
