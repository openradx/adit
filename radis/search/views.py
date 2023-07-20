from typing import Any, Dict

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View

from radis.vespa_app import vespa_client

from .forms import SearchForm


class SearchView(View):
    async def get(self, request, *args, **kwargs):
        form = SearchForm(request.GET)
        context = {"form": form}

        query = request.GET.get("q")
        if query:
            results = vespa_client.query(
                {
                    "yql": "select * from sources * where userQuery()",
                    "hits": 100,
                    "query": query,
                }
            )

        return render(request, "search/search.html", context)
