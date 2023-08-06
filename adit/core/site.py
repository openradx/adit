from django.conf import settings
from django.middleware.csrf import get_token

nav_menu_items = []
job_stats_collectors = []


def register_main_menu_item(url_name, label):
    nav_menu_items.append({"url_name": url_name, "label": label})


def register_job_stats_collector(job_stats):
    job_stats_collectors.append(job_stats)


def base_context_processor(request):
    return {
        "version": settings.ADIT_VERSION,
        "base_url": settings.BASE_URL,
        "support_email": settings.SUPPORT_EMAIL,
        "nav_menu_items": nav_menu_items,
        "public": {
            "debug": settings.DEBUG,
            "csrf_token": get_token(request),
        },
    }
