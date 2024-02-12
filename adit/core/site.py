from typing import TYPE_CHECKING, Any, Callable, NamedTuple

from django.conf import settings
from django.http import HttpRequest
from django.middleware.csrf import get_token

if TYPE_CHECKING:
    from .models import DicomJob
    from .processors import DicomTaskProcessor


class NavMenuItem(NamedTuple):
    url_name: str
    label: str


nav_menu_items: list[NavMenuItem] = []


def register_main_menu_item(url_name: str, label: str) -> None:
    nav_menu_items.append(NavMenuItem(url_name, label))


class JobStats(NamedTuple):
    job_name: str
    url_name: str
    counts: dict["DicomJob.Status", int]


JobStatsCollector = Callable[[], JobStats]


job_stats_collectors: list[JobStatsCollector] = []


def register_job_stats_collector(collector: JobStatsCollector) -> None:
    job_stats_collectors.append(collector)


dicom_processors: dict[str, type["DicomTaskProcessor"]] = {}


def register_dicom_processor(model_label: str, dicom_processor: type["DicomTaskProcessor"]) -> None:
    dicom_processors[model_label] = dicom_processor


def base_context_processor(request: HttpRequest) -> dict[str, Any]:
    from .utils.auth_utils import is_logged_in_user

    theme = "auto"
    theme_color = "light"
    user = request.user
    if is_logged_in_user(user):
        preferences = user.preferences
        theme = preferences.get("theme", theme)
        theme_color = preferences.get("theme_color", theme_color)

    return {
        "version": settings.ADIT_VERSION,
        "base_url": settings.BASE_URL,
        "support_email": settings.SUPPORT_EMAIL,
        "nav_menu_items": nav_menu_items,
        "theme": theme,
        "theme_color": theme_color,
        # Variables in public are also available on the client via JavaScript,
        # see base_generic.html
        "public": {
            "debug": settings.DEBUG,
            "csrf_token": get_token(request),
        },
    }
