from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import DetailView, TemplateView
from django_tables2 import SingleTableMixin

from adit.core.mixins import OwnerRequiredMixin, PageSizeSelectMixin, RelatedFilterMixin
from adit.core.views import (
    DicomJobCancelView,
    DicomJobCreateView,
    DicomJobDeleteView,
    DicomJobRestartView,
    DicomJobResumeView,
    DicomJobRetryView,
    DicomJobVerifyView,
    DicomTaskDetailView,
    TransferJobListView,
)

from .filters import BatchTransferJobFilter, BatchTransferTaskFilter
from .forms import BatchTransferJobForm
from .models import BatchTransferJob, BatchTransferSettings, BatchTransferTask
from .tables import BatchTransferJobTable, BatchTransferTaskTable


class BatchTransferJobListView(TransferJobListView):
    model = BatchTransferJob
    table_class = BatchTransferJobTable
    filterset_class = BatchTransferJobFilter
    template_name = "batch_transfer/batch_transfer_job_list.html"


class BatchTransferJobCreateView(DicomJobCreateView):
    model = BatchTransferJob
    form_class = BatchTransferJobForm
    template_name = "batch_transfer/batch_transfer_job_form.html"
    permission_required = "batch_transfer.add_batchtransferjob"

    def form_valid(self, form):
        user = self.request.user
        form.instance.owner = user

        response = super().form_valid(form)

        # Do it after an ongoing transaction (even if it is currently
        # unnecessary as ATOMIC_REQUESTS is False), see also
        # https://spapas.github.io/2019/02/25/django-fix-async-db/
        # Currently I am not using it because it is hard to test, but there
        # it is already fixed in an upcoming release, see
        # https://code.djangoproject.com/ticket/30457
        # TODO transaction.on_commit(lambda: enqueue_batch_job(self.object.id))
        job = self.object
        if user.is_staff or settings.BATCH_TRANSFER_UNVERIFIED:
            job.status = BatchTransferJob.Status.PENDING
            job.save()
            job.delay()

        return response

    def dispatch(self, request, *args, **kwargs):
        batch_transfer_settings = BatchTransferSettings.get()
        if batch_transfer_settings.locked and not request.user.is_staff:
            return TemplateView.as_view(template_name="batch_transfer/batch_transfer_locked.html")(
                request
            )
        return super().dispatch(request, *args, **kwargs)


class BatchTransferJobDetailView(
    LoginRequiredMixin,
    OwnerRequiredMixin,
    SingleTableMixin,
    RelatedFilterMixin,
    PageSizeSelectMixin,
    DetailView,
):
    table_class = BatchTransferTaskTable
    filterset_class = BatchTransferTaskFilter
    model = BatchTransferJob
    context_object_name = "job"
    template_name = "batch_transfer/batch_transfer_job_detail.html"

    def get_filter_queryset(self):
        job = self.get_object()
        return job.tasks


class BatchTransferJobDeleteView(DicomJobDeleteView):
    model = BatchTransferJob
    success_url = reverse_lazy("batch_transfer_job_list")


class BatchTransferJobVerifyView(DicomJobVerifyView):
    model = BatchTransferJob


class BatchTransferJobCancelView(DicomJobCancelView):
    model = BatchTransferJob


class BatchTransferJobResumeView(DicomJobResumeView):
    model = BatchTransferJob


class BatchTransferJobRetryView(DicomJobRetryView):
    model = BatchTransferJob


class BatchTransferJobRestartView(DicomJobRestartView):
    model = BatchTransferJob


class BatchTransferTaskDetailView(DicomTaskDetailView):
    model = BatchTransferTask
    job_url_name = "batch_transfer_job_detail"
    template_name = "batch_transfer/batch_transfer_task_detail.html"
