import re
from django.views.generic import View, TemplateView
from django.views.generic.edit import DeleteView, CreateView
from django.views.generic.detail import SingleObjectMixin
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import re_path, reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import SuspiciousOperation
from django.contrib import messages
from django.conf import settings
from django.forms.formsets import ORDERING_FIELD_NAME
from rest_framework import generics
from django_tables2 import SingleTableMixin
from django_filters.views import FilterView
from revproxy.views import ProxyView
from .models import TransferJob
from .tables import TransferJobTable
from .filters import TransferJobFilter
from .mixins import OwnerRequiredMixin, PageSizeSelectMixin
from .serializers import TransferJobListSerializer


class TransferJobListView(
    LoginRequiredMixin, SingleTableMixin, PageSizeSelectMixin, FilterView
):
    table_class = TransferJobTable
    template_name = "core/transfer_job_table.html"
    filterset_class = TransferJobFilter

    def get_queryset(self):
        return TransferJob.objects.select_related("source", "destination").filter(
            owner=self.request.user
        )


def redirect_to_job_detail_view(request, pk):
    queryset = TransferJob.objects.select_subclasses()
    job = get_object_or_404(queryset, pk=pk)
    return redirect(job)


class TransferJobDeleteView(LoginRequiredMixin, OwnerRequiredMixin, DeleteView):
    model = TransferJob
    owner_accessor = "owner"
    success_url = reverse_lazy("transfer_job_list")
    success_message = "Job with ID %(id)s was deleted successfully"

    def delete(self, request, *args, **kwargs):
        job = self.get_object()
        if not job.is_deletable():
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not deletable."
            )

        # As SuccessMessageMixin does not work in DeleteView we have to do
        # it manually (https://code.djangoproject.com/ticket/21936)
        messages.success(self.request, self.success_message % job.__dict__)
        return super().delete(request, *args, **kwargs)


class TransferJobCancelView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    model = TransferJob
    owner_accessor = "owner"
    success_message = "Job with ID %(id)n was canceled"

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        job = self.get_object()
        if not job.is_cancelable():
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} is not cancelable."
            )

        job.status = TransferJob.Status.CANCELING
        job.save()
        messages.success(self.request, self.success_message % job.__dict__)
        redirect(job)


class TransferJobVerifyView(
    LoginRequiredMixin, OwnerRequiredMixin, SingleObjectMixin, View
):
    queryset = TransferJob.objects.select_subclasses()
    owner_accessor = "owner"
    success_message = "Transfer job with ID %(id)s was verified"

    def post(self, request, *args, **kwargs):  # pylint: disable=unused-argument
        job = self.get_object()
        if job.is_verified():
            raise SuspiciousOperation(
                f"Job with ID {job.id} and status {job.get_status_display()} was already verified."
            )

        job.status = TransferJob.Status.PENDING
        job.save()
        job.delay()
        messages.success(self.request, self.success_message % job.__dict__)
        redirect(job)


class FlowerProxyView(UserPassesTestMixin, ProxyView):
    """A reverse proxy view to access the Flower Celery admin tool.

    By using a reverse proxy we can use the Django authentication
    to check for an logged in admin user.
    Code from https://stackoverflow.com/a/61997024/166229
    """

    upstream = "http://{}:{}".format(settings.FLOWER_HOST, settings.FLOWER_PORT)
    url_prefix = "flower"
    rewrite = ((r"^/{}$".format(url_prefix), r"/{}/".format(url_prefix)),)

    def test_func(self):
        return self.request.user.is_staff

    @classmethod
    def as_url(cls):
        return re_path(r"^(?P<path>{}.*)$".format(cls.url_prefix), cls.as_view())


class TransferJobListAPIView(generics.ListAPIView):
    serializer_class = TransferJobListSerializer

    def get_queryset(self):
        return TransferJob.objects.filter(owner=self.request.user)


class InlineFormSetCreateView(CreateView):
    formset_class = None
    formset_prefix = None

    def add_formset_form(self, prefix):
        cp = self.request.POST.copy()
        cp[f"{prefix}-TOTAL_FORMS"] = int(cp[f"{prefix}-TOTAL_FORMS"]) + 1
        return cp

    def delete_formset_form(self, idx_to_delete, prefix):
        cp = self.request.POST.copy()
        cp[f"{prefix}-TOTAL_FORMS"] = int(cp[f"{prefix}-TOTAL_FORMS"]) - 1
        regex = prefix + r"-(\d+)-"
        filtered = {}
        for k, v in cp.items():
            match = re.findall(regex, k)
            if match:
                idx = int(match[0])
                if idx == idx_to_delete:
                    continue
                if idx > idx_to_delete:
                    k = re.sub(regex, f"{prefix}-{idx-1}-", k)
                filtered[k] = v
            else:
                filtered[k] = v
        return filtered

    def clear_errors(self, form_or_formset):
        # Hide all errors of a form or formset.
        # Found only this hacky way.
        # See https://stackoverflow.com/questions/64402527
        # pylint: disable=protected-access
        form_or_formset._errors = {}
        if hasattr(form_or_formset, "forms"):
            for form in form_or_formset.forms:
                self.clear_errors(form)

    def post(self, request, *args, **kwargs):
        self.object = None

        form = self.get_form()

        if request.POST.get("add_formset_form"):
            post_data = self.add_formset_form(self.formset_prefix)
            formset = self.formset_class(post_data)  # pylint: disable=not-callable
            return self.render_changed_formset(form, formset)

        if request.POST.get("delete_formset_form"):
            idx_to_delete = int(request.POST.get("delete_formset_form"))
            post_data = self.delete_formset_form(idx_to_delete, self.formset_prefix)
            formset = self.formset_class(post_data)  # pylint: disable=not-callable
            return self.render_changed_formset(form, formset)

        formset = self.formset_class(request.POST)  # pylint: disable=not-callable
        if form.is_valid() and formset.is_valid():
            return self.form_and_formset_valid(form, formset)

        return self.form_or_formset_invalid(form, formset)

    def render_changed_formset(self, form, formset):
        self.clear_errors(form)
        self.clear_errors(formset)
        return self.form_or_formset_invalid(form, formset)

    def form_invalid(self, form):
        raise AttributeError(
            "A 'InlineFormSetCreateView' does not have a 'form_invalid' attribute. "
            "Use 'form_or_formset_invalid' instead."
        )

    def form_valid(self, form):
        raise AttributeError(
            "A 'InlineFormSetCreateView' does not have a 'form_valid' attribute. "
            "Use 'form_and_formset_valid' instead."
        )

    def form_or_formset_invalid(self, form, formset):
        return self.render_to_response(
            self.get_context_data(form=form, formset=formset)
        )

    def form_and_formset_valid(self, form, formset):
        response = super().form_valid(form)
        formset.instance = self.object
        for idx, formset_form in enumerate(formset.ordered_forms):
            formset_form.instance.order = (
                formset_form.cleaned_data.get(ORDERING_FIELD_NAME) or idx + 1
            )
        formset.save()
        return response

    def get_context_data(self, **kwargs):
        if "formset" not in kwargs:
            kwargs["formset"] = self.formset_class()  # pylint: disable=not-callable
        return super().get_context_data(**kwargs)
