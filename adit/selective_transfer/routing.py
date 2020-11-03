from django.urls import path
from .consumers import SelectiveTransferConsumer

websocket_urlpatterns = [
    path("ws/selective-transfer", SelectiveTransferConsumer.as_asgi()),
]
