from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django_tables2 import SingleTableMixin

from .models import ReportCollection


class ReportCollectionListView(LoginRequiredMixin, SingleTableMixin, ListView):
    model = ReportCollection
    template_name = "collections/collection_list.html"
