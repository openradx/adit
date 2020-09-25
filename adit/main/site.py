from django.conf import settings

nav_menu_items = []
job_detail_views = {}
job_type_choices = []


def register_main_menu_item(url_name, label):
    nav_menu_items.append({"url_name": url_name, "label": label})


def register_transfer_job(type_key, type_name, detail_view):
    if type_key in job_detail_views:
        raise KeyError(
            f"The key {type_key} for job type {type_name} is already registered."
        )

    job_detail_views[type_key] = detail_view
    job_type_choices.append((type_key, type_name))


def base_context_processor(request):
    return {
        "BASE_URL": settings.BASE_URL,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "nav_menu_items": nav_menu_items,
    }
