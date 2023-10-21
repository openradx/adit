from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import BadRequest
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views import View

from radis.core.types import AuthenticatedRequest

from .models import ReportQuery
from .serializers import SearchParamsSerializer
from .utils.search_utils import get_collection_counts


class SearchView(LoginRequiredMixin, View):
    def get(self, request: AuthenticatedRequest, *args, **kwargs):
        serializer = SearchParamsSerializer(data=request.GET)

        if not serializer.is_valid():
            raise BadRequest("Invalid GET parameters.")

        query: str = serializer.validated_data["query"]
        page_number: int = serializer.validated_data["page"]
        page_size: int = serializer.validated_data["per_page"]
        offset = (page_number - 1) * page_size

        context = {}
        if query:
            result = ReportQuery.query_reports(query, offset, page_size)
            total_count = result.total_count
            paginator = Paginator(range(total_count), page_size)
            page = paginator.get_page(page_number)

            documents_ids = [report.document_id for report in result.reports]
            collection_counts = get_collection_counts(request.user, documents_ids)

            context["query"] = query
            context["offset"] = offset
            context["paginator"] = paginator
            context["page_obj"] = page
            context["total_count"] = total_count
            context["reports"] = result.reports
            context["collection_counts"] = collection_counts

        return render(request, "search/search.html", context)
