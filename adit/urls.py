"""adit URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin-the-great/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("accounts/", include("shared.accounts.urls")),
    path("api/", include("adit.api.urls")),
    path("", include("adit.core.urls")),
    path("selective-transfer/", include("adit.selective_transfer.urls")),
    path("batch-transfer/", include("adit.batch_transfer.urls")),
    path("batch-query/", include("adit.batch_query.urls")),
    path("dicom-explorer/", include("adit.dicom_explorer.urls")),
    path("token-authentication/", include("shared.token_authentication.urls")),
    path("dicom-web/", include("adit.dicom_web.urls")),
    path("sandbox/", include("adit.sandbox.urls")),
]

# Django loginas
urlpatterns += [path("admin/", include("loginas.urls"))]

# Debug Toolbar in Debug mode only
if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__reload__/", include("django_browser_reload.urls")),
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
