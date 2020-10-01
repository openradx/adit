import re
import pytz
from django.views.generic import TemplateView
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from .models import AppSettings


class MaintenanceMiddleware:
    """Render a maintenance template if in maintenance mode.

    Adapted from http://blog.ankitjaiswal.tech/put-your-django-site-on-maintenanceoffline-mode/
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        login_request = request.path == reverse("auth_login")
        logout_request = request.path == reverse("auth_logout")
        if login_request or logout_request:
            return self.get_response(request)

        app_settings = AppSettings.objects.first()
        in_maintenance = app_settings.maintenance_mode
        if in_maintenance and not request.user.is_staff:
            return TemplateView.as_view(template_name="main/maintenance.html")(
                request
            ).render()
        else:
            response = self.get_response(request)
            if (
                self.is_html_response(response)
                and in_maintenance
                and request.user.is_staff
            ):
                response.content = re.sub(
                    r"<body.*>",
                    r"\g<0>Site is in maintenance mode!",
                    response.content.decode("utf-8"),
                )
            return response

    def is_html_response(self, response):
        return response["Content-Type"].startswith("text/html")


class TimezoneMiddleware:  # pylint: disable=too-few-public-methods
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = request.session.get("django_timezone")
        if not tzname:
            tzname = settings.DEFAULT_TIME_ZONE
        if tzname:
            timezone.activate(pytz.timezone(tzname))
        else:
            timezone.deactivate()
        return self.get_response(request)
