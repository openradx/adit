from django.core.paginator import Paginator
from django.shortcuts import render
from django.views import View

from radis.core.vespa_app import vespa_app

from .forms import SearchForm


class SearchView(View):
    async def get(self, request, *args, **kwargs):
        form = SearchForm(request.GET)
        context = {
            "form": form,
            "searched": False,
            "hits": [],
        }

        query = request.GET.get("q")
        page = request.GET.get("page", 10)
        per_page = request.GET.get("per_page", 100)
        if query:
            response = await vespa_app.query_reports(query, page, per_page)
            total_count = response.json["root"]["fields"]["totalCount"]
            paginator = Paginator(range(total_count), per_page)
            page = paginator.get_page(page)
            context["paginator"] = paginator
            context["page"] = page
            context["searched"] = True
            context["hits"] = response.hits

        return render(request, "search/search.html", context)
