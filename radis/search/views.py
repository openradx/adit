from django.core.exceptions import BadRequest
from django.core.paginator import Paginator
from django.shortcuts import render
from django.views import View

from radis.core.models import QueryResult
from radis.core.vespa_app import vespa_app

from .forms import SearchForm
from .serializers import SearchParamsSerializer


class SearchView(View):
    def get(self, request, *args, **kwargs):
        form = SearchForm(request.GET)
        context = {
            "form": form,
            "searched": False,
            "hits": [],
        }

        serializer = SearchParamsSerializer(data=request.GET)

        if not serializer.is_valid():
            raise BadRequest("Invalid GET parameters.")

        query = serializer.validated_data["query"]
        page = serializer.validated_data["page"]
        per_page = serializer.validated_data["per_page"]

        if query:
            response = vespa_app.query_reports(query, page, per_page)
            result = QueryResult.from_response(response)
            total_count = result.total_count
            paginator = Paginator(range(total_count), per_page)
            page = paginator.get_page(page)
            context["paginator"] = paginator
            context["page"] = page
            context["searched"] = True
            context["reports"] = result.reports

        return render(request, "search/search.html", context)
