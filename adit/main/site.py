from django.conf import settings

nav_menu_items = []
job_type_choices = []
job_detail_views = {}
job_delay_funcs = {}


def register_main_menu_item(url_name, label):
    nav_menu_items.append({"url_name": url_name, "label": label})


def register_transfer_job(type_key, type_name, detail_view, delay_func):
    if type_key in job_detail_views:
        raise KeyError(f"A transfer job with key {type_key} is already registered.")

    job_type_choices.append((type_key, type_name))
    job_detail_views[type_key] = detail_view
    job_delay_funcs[type_key] = delay_func


def base_context_processor(request):
    return {
        "BASE_URL": settings.BASE_URL,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "nav_menu_items": nav_menu_items,
    }
