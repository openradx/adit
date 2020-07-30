from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import CreateView
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import PermissionRequiredMixin
from main.mixins import OwnerRequiredMixin
from main.models import DicomNode
from .models import AppSettings, BatchTransferJob
from .forms import BatchTransferJobForm
from .utils.task_utils import must_be_scheduled, next_batch_slot
from .tasks import batch_transfer_task


class BatchTransferJobCreate(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = BatchTransferJob
    form_class = BatchTransferJobForm
    template_name = "batch_transfer/batch_transfer_job_form.html"
    permission_required = "batch_transfer.add_batchtransferjob"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"user": self.request.user})
        return kwargs

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)

        # Do it after an ongoing transaction (even if it is currently
        # unnecessary as ATOMIC_REQUESTS is False), see also
        # https://spapas.github.io/2019/02/25/django-fix-async-db/
        # Currently I am not using it because it is hard to test, but there
        # it is already fixed in an upcoming release, see
        # https://code.djangoproject.com/ticket/30457
        # transaction.on_commit(lambda: enqueue_batch_job(self.object.id))
        batch_job_id = self.object.id
        if must_be_scheduled():
            next_slot = next_batch_slot()
            batch_transfer_task.apply_async(args=[batch_job_id], eta=next_slot)
        else:
            batch_transfer_task.delay(batch_job_id)

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["node_types"] = {}
        for node in DicomNode.objects.all():
            if node.node_type == DicomNode.NodeType.SERVER:
                context["node_types"][node.id] = "server"
            elif node.node_type == DicomNode.NodeType.FOLDER:
                context["node_types"][node.id] = "folder"
        return context

    def dispatch(self, request, *args, **kwargs):
        app_settings = AppSettings.objects.first()
        if app_settings.batch_transfer_locked and not request.user.is_staff:
            return TemplateView.as_view(
                template_name="batch_transfer/batch_transfer_locked.html"
            )(request)
        return super().dispatch(request, *args, **kwargs)


class BatchTransferJobDetail(LoginRequiredMixin, OwnerRequiredMixin, DetailView):
    model = BatchTransferJob
    context_object_name = "job"
    template_name = "batch_transfer/batch_transfer_job_detail.html"
    owner_accessor = "created_by"
