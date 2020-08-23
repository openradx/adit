from rest_framework import generics
from rest_framework import permissions
from rest_framework.exceptions import MethodNotAllowed
from main.models import TransferJob
from .serializers import TransferJobListSerializer, TransferJobCreateSerializer


class TransferJobListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TransferJob.objects.filter(created_by=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "GET":
            return TransferJobListSerializer

        if self.request.method == "POST":
            return TransferJobCreateSerializer

        raise MethodNotAllowed(self.request.method)
