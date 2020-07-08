import re

from django.views.generic import TemplateView
from django.urls import reverse
from .models import SiteConfig

class MaintenanceMiddleware:
    """Render a maintenance template if in maintenance mode.

    Adapted from http://blog.ankitjaiswal.tech/put-your-django-site-on-maintenanceoffline-mode/
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        login_request = request.path == reverse('auth_login')
        logout_request = request.path == reverse('auth_logout')
        if login_request or logout_request:
            return self.get_response(request)

        self.config = SiteConfig.objects.first()
        in_maintenance = self.config.maintenance_mode
        if in_maintenance and not request.user.is_staff:
            return TemplateView.as_view(
                    template_name='main/maintenance.html')(request).render()
        else:
            response = self.get_response(request)
            if self.is_html_response(response) and in_maintenance and request.user.is_staff:
                response.content = re.sub(r'<body.*>', r'\g<0>Site is in maintenance mode!',
                        response.content.decode('utf-8'))
            return response

    def is_html_response(self, response):
        return response['Content-Type'].startswith('text/html')