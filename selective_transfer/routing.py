from django.urls import path
from .consumers import QueryStudiesConsumer

websocket_urlpatterns = [
    path("ws/query-studies", QueryStudiesConsumer),
]
