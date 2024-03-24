import re

import pytz
from django.conf import settings
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone

from .models import ProjectSettings


def is_html_response(response):
    return response.has_header("Content-Type") and response["Content-Type"].startswith("text/html")


class BaseMaintenanceMiddleware:
    """Render a maintenance template if in maintenance mode.

    Adapted from http://blog.ankitjaiswal.tech/put-your-django-site-on-maintenanceoffline-mode/
    """

    project_settings: type[ProjectSettings]
    template_name: str

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        login_request = request.path == reverse("auth_login")
        logout_request = request.path == reverse("auth_logout")
        if login_request or logout_request:
            return self.get_response(request)

        settings = self.project_settings.get()
        assert settings
        in_maintenance = settings.maintenance_mode
        if in_maintenance and not request.user.is_staff:
            response = TemplateResponse(request, self.template_name)
            return response.render()

        response = self.get_response(request)
        if is_html_response(response) and in_maintenance and request.user.is_staff:
            response.content = re.sub(
                r"<body.*>",
                r"\g<0><div class='maintenance-hint'>Site is in maintenance mode!</div>",
                response.content.decode("utf-8"),
            )
        return response


class TimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = request.session.get("django_timezone")
        if not tzname:
            tzname = settings.USER_TIME_ZONE
        if tzname:
            timezone.activate(pytz.timezone(tzname))
        else:
            timezone.deactivate()
        return self.get_response(request)
