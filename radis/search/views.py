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
        if query:
            results = await vespa_app.query_reports(query)
            context["searched"] = True
            context["hits"] = results.hits

        return render(request, "search/search.html", context)
