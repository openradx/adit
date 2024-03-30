from typing import Any, NamedTuple

from django.conf import settings
from django.http import HttpRequest
from django.middleware.csrf import get_token

THEME_PREFERENCE_KEY = "theme"


class MainMenuItem(NamedTuple):
    url_name: str
    label: str


main_menu_items: list[MainMenuItem] = []


def register_main_menu_item(url_name: str, label: str) -> None:
    main_menu_items.append(MainMenuItem(url_name, label))


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
        "version": settings.PROJECT_VERSION,
        "support_email": settings.SUPPORT_EMAIL,
        "main_menu_items": main_menu_items,
        "theme": theme,
        "theme_color": theme_color,
        # This data will be available on the client, see common_layout.html
        "public": {
            "debug": settings.DEBUG,
            "csrf_token": get_token(request),
            "theme_preference_key": THEME_PREFERENCE_KEY,
        },
    }
