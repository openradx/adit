from django.conf import settings
from rest_framework.views import APIView


class DicomWebAPIView(APIView):
    query: dict = {}
    level: str
    TMP_FOLDER: str = settings.WADO_TMP_FOLDER
