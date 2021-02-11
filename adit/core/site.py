from django.conf import settings

nav_menu_items = []
job_stats_collectors = []


def register_main_menu_item(url_name, label):
    nav_menu_items.append({"url_name": url_name, "label": label})


def register_job_stats_collector(job_stats):
    job_stats_collectors.append(job_stats)


def base_context_processor(request):
    return {
        "ADIT_VERSION": settings.ADIT_VERSION,
        "BASE_URL": settings.BASE_URL,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "nav_menu_items": nav_menu_items,
    }
