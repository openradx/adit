from django.views.generic import View
from django.http import HttpResponse, JsonResponse

from adit.core.models import DicomServer

import xnat


class CheckXnatSourceView(View):
    def get(self, request, *args, **kwargs):
        name = kwargs.get("name", False)
        if not name:
            return HttpResponse(False)
        server = DicomServer.objects.filter(name=name)
        
        if len(server) < 1:
            return HttpResponse(False)
        elif server[0].xnat_server:
            return HttpResponse(True)
        else:
            return HttpResponse(False)

class FindXnatProjectsView(View):
    def get(self, request, *args, **kwargs):
        name = kwargs.get("name", False)
        if not name:
            return JsonResponse([])
        server = DicomServer.objects.filter(name=name)[0]
        session = xnat.connect(
            server.xnat_root_url, 
            user=server.xnat_username, 
            password=server.xnat_password
        )
        return JsonResponse(list(session.projects), safe=False)

