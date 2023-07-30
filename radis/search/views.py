from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import BadRequest
from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import render
from django.views import View

from radis.core.vespa_app import vespa_app

from .serializers import SearchParamsSerializer


class SearchView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, *args, **kwargs):
        context = {}

        serializer = SearchParamsSerializer(data=request.GET)

        if not serializer.is_valid():
            raise BadRequest("Invalid GET parameters.")

        query = serializer.validated_data["query"]
        page = serializer.validated_data["page"]
        per_page = serializer.validated_data["per_page"]

        if query:
            result = vespa_app.query_reports(query, page, per_page)
            total_count = result.total_count
            paginator = Paginator(range(total_count), per_page)
            page = paginator.get_page(page)
            context["query"] = query
            context["paginator"] = paginator
            context["page"] = page
            context["total_count"] = total_count
            context["reports"] = result.reports

        return render(request, "search/search.html", context)


class PreviewView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, doc_id: str):
        report = vespa_app.get_report(doc_id)
        return render(request, "search/preview.html", {"report": report})
