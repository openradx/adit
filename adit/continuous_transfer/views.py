from django.conf import settings
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from adit.core.utils.permission_utils import is_logged_in_user, is_staff_user
from adit.core.views import (
    DicomJobCancelView,
    DicomJobCreateView,
    DicomJobDeleteView,
    DicomJobDetailView,
    DicomJobRestartView,
    DicomJobResumeView,
    DicomJobRetryView,
    DicomJobVerifyView,
    DicomTaskDetailView,
    TransferJobListView,
)

from .filters import ContinuousTransferJobFilter, ContinuousTransferTaskFilter
from .forms import ContinuousTransferJobForm
from .models import ContinuousTransferJob, ContinuousTransferSettings, ContinuousTransferTask
from .tables import ContinuousTransferJobTable, ContinuousTransferTaskTable


class ContinuousTransferJobListView(TransferJobListView):
    model = ContinuousTransferJob
    table_class = ContinuousTransferJobTable
    filterset_class = ContinuousTransferJobFilter
    template_name = "continuous_transfer/continuous_transfer_job_list.html"


class ContinuousTransferJobCreateView(DicomJobCreateView):
    model = ContinuousTransferJob
    form_class = ContinuousTransferJobForm
    template_name = "continuous_transfer/continuous_transfer_job_form.html"
    permission_required = "continuous_transfer.add_continuoustransferjob"
    object: ContinuousTransferJob

    def form_valid(self, form):
        user = self.request.user
        if not is_logged_in_user(user):
            raise AssertionError("User is not logged in.")

        form.instance.owner = user
        response = super().form_valid(form)

        # Do it after an ongoing transaction (even if it is currently
        # unnecessary as ATOMIC_REQUESTS is False), see also
        # https://spapas.github.io/2019/02/25/django-fix-async-db/
        # Currently I am not using it because it is hard to test, but there
        # it is already fixed in an upcoming release, see
        # https://code.djangoproject.com/ticket/30457
        # TODO transaction.on_commit(lambda: enqueue_continuous_job(self.object.id))
        job = self.object  # set by super().form_valid(form)
        if user.is_staff or settings.CONTINUOUS_TRANSFER_UNVERIFIED:
            job.status = ContinuousTransferJob.Status.PENDING
            job.save()
            job.delay()

        return response

    def dispatch(self, request, *args, **kwargs):
        continuous_transfer_settings = ContinuousTransferSettings.get()
        assert continuous_transfer_settings

        user = request.user
        if continuous_transfer_settings.locked and not is_staff_user(user):
            return TemplateView.as_view(
                template_name="continuous_transfer/continuous_transfer_locked.html"
            )(request)
        return super().dispatch(request, *args, **kwargs)


class ContinuousTransferJobDetailView(DicomJobDetailView):
    table_class = ContinuousTransferTaskTable
    filterset_class = ContinuousTransferTaskFilter
    model = ContinuousTransferJob
    context_object_name = "job"
    template_name = "continuous_transfer/continuous_transfer_job_detail.html"


class ContinuousTransferJobDeleteView(DicomJobDeleteView):
    model = ContinuousTransferJob
    success_url = reverse_lazy("continuous_transfer_job_list")


class ContinuousTransferJobVerifyView(DicomJobVerifyView):
    model = ContinuousTransferJob


class ContinuousTransferJobCancelView(DicomJobCancelView):
    model = ContinuousTransferJob


class ContinuousTransferJobResumeView(DicomJobResumeView):
    model = ContinuousTransferJob


class ContinuousTransferJobRetryView(DicomJobRetryView):
    model = ContinuousTransferJob


class ContinuousTransferJobRestartView(DicomJobRestartView):
    model = ContinuousTransferJob


class ContinuousTransferTaskDetailView(DicomTaskDetailView):
    model = ContinuousTransferTask
    job_url_name = "continuous_transfer_job_detail"
    template_name = "continuous_transfer/continuous_transfer_task_detail.html"
