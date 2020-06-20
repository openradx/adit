from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import TransferJob


class TransferJobList(LoginRequiredMixin, ListView):
    model = TransferJob
    context_object_name = 'jobs'
    paginate_by = 5

    def get_queryset(self, *args, **kwargs):
        if self.kwargs:
            owner = self.request.user
            return TransferJob.objects.filter(
                created_by=owner,
                status=self.kwargs['status']
            ).order_by('-created_at')
        else:
            return TransferJob.objects.all().order_by('-created_at')