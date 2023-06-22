import json

from rest_framework import renderers


class ApplicationDicomJsonRenderer(renderers.BaseRenderer):
    media_type = "application/dicom+json"
    format = "json"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return json.dumps(data)
