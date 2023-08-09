from asgiref.sync import sync_to_async
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView


class SandboxListView(TemplateView):
    template_name = "sandbox/sandbox_list.html"


@staff_member_required
def sandbox_messages(request: HttpRequest) -> HttpResponse:
    messages.add_message(request, messages.SUCCESS, "This message is server generated!")
    return render(request, "sandbox/sandbox_messages.html", {})


# Cave, LoginRequiredMixin won't work with async views! One has to implement it himself.
class AsyncSandboxClassView(View):
    async def get(self, request: HttpRequest) -> HttpResponse:
        return await sync_to_async(render)(request, "sandbox/sandbox_test.html")
