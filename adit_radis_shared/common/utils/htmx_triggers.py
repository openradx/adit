from typing import Literal

from django.http import HttpResponse
from django_htmx.http import trigger_client_event


def trigger_toast(
    response: HttpResponse | None = None,
    level: Literal["success", "warning", "error"] = "success",
    title: str = "",
    text: str = "",
):
    """Helper function to trigger a toast on the client side using HTMX"""
    if not response:
        response = HttpResponse(status=200)

    response = trigger_client_event(
        response,
        "toast",
        {
            "level": level,
            "title": title,
            "text": text,
        },
    )
    return response
