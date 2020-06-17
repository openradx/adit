from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import TransferJob

def index(request):
    return render(request, 'main/index.html', {})


class TransferJobList(LoginRequiredMixin, ListView):
    model = TransferJob