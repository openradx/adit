from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import BadRequest
from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import render
from django.views import View

from radis.collections.models import CollectedReport
from radis.core.types import AuthenticatedRequest
from radis.core.vespa_app import vespa_app

from .serializers import SearchParamsSerializer


class SearchReportsView(LoginRequiredMixin, View):
    def get(self, request: AuthenticatedRequest, *args, **kwargs):
        serializer = SearchParamsSerializer(data=request.GET)

        if not serializer.is_valid():
            raise BadRequest("Invalid GET parameters.")

        query = serializer.validated_data["query"]
        page_number = serializer.validated_data["page"]
        page_size = serializer.validated_data["per_page"]
        offset = (page_number - 1) * page_size

        context = {}
        if query:
            result = vespa_app.query_reports(query, offset, page_size)
            total_count = result.total_count
            paginator = Paginator(range(total_count), page_size)
            page = paginator.get_page(page_number)

            owner_id = request.user.id
            documents_ids = [report.document_id for report in result.reports]
            collection_counts = CollectedReport.objects.get_collection_counts(
                owner_id=owner_id, document_ids=documents_ids
            )

            context["query"] = query
            context["offset"] = offset
            context["paginator"] = paginator
            context["page_obj"] = page
            context["total_count"] = total_count
            context["reports"] = result.reports
            context["collection_counts"] = collection_counts

        return render(request, "reports/search_reports.html", context)


class ReportDetailView(View):
    def get(self, request: HttpRequest, document_id: str):
        report = vespa_app.get_report(document_id)
        return render(request, "reports/report_detail.html", {"report": report})


class ReportPreviewView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, document_id: str):
        report = vespa_app.get_report(document_id)
        return render(request, "reports/report_preview.html", {"report": report})
