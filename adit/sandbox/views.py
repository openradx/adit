from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView


class SandboxListView(TemplateView):
    template_name = "sandbox/sandbox_list.html"


@staff_member_required
def sandbox_messages(request: HttpRequest) -> HttpResponse:
    messages.add_message(request, messages.SUCCESS, "This message is server generated!")
    return render(request, "sandbox/sandbox_messages.html", {})
