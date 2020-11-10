from rest_framework import generics
from adit.core.models import TransferJob
from .serializers import TransferJobListSerializer


class TransferJobListAPIView(generics.ListAPIView):
    serializer_class = TransferJobListSerializer

    def get_queryset(self):
        return TransferJob.objects.filter(owner=self.request.user)
