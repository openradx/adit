from rest_framework import renderers
from django.http import JsonResponse, FileResponse
import json

class DicomMultipartRenderer(renderers.BaseRenderer):
    media_type = "multipart/related"
    format = "txt"

    def create_response(self, file_path=None, file=None, type=None, boundary=None):
        subtype = ""
        bound = ""
        if not type is None:
            subtype = f"; type={type}"
        if not boundary is None:
            bound = f"; boundary={boundary}"
        if not file_path is None:
            f = open(file_path, "rb")
            response  = FileResponse(
                f,
                content_type = "multipart/related" + subtype + bound
            )
            return response
        elif not file is None:
            return FileResponse(file, content_type="multipart/related")

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data

class DicomJsonRenderer(renderers.BaseRenderer):
    media_type = "application/dicom+json"
    format = "json"

    def create_response(self, file_path=None, file=None):
        if not file_path is None:
            with open(file_path, "r") as f:
                response = JsonResponse(json.load(f), safe=False)
            return response
        elif not file is None:
            return JsonResponse(file, safe=False)

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data