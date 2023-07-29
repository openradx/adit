from django.http import HttpRequest
from django.shortcuts import render
from django.views import View
from rest_framework import status

from radis.core.vespa_app import vespa_app


class ReportDetailView(View):
    def get(self, request: HttpRequest, doc_id: str):
        client = vespa_app.get_client()
        response = client.get_data("report", doc_id)
        context = {"doc_id": doc_id, "document": None}
        if response.get_status_code == status.HTTP_200_OK:
            context["document"] = response.get_json()["fields"]

        render(request, "reports/report_detail.html", context)
