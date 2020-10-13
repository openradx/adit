from django.conf import settings

nav_menu_items = []
job_type_choices = []


def register_main_menu_item(url_name, label):
    nav_menu_items.append({"url_name": url_name, "label": label})


def register_transfer_job(job_type_key, job_type_name):
    if any(job_type[0] == job_type_key for job_type in job_type_choices):
        raise KeyError(
            f"A transfer job with type key {job_type_key} is already registered."
        )

    if any(job_type[1] == job_type_name for job_type in job_type_choices):
        raise KeyError(
            f"A transfer job with type name {job_type_name} is already registered."
        )

    job_type_choices.append((job_type_key, job_type_name))


def base_context_processor(request):
    return {
        "BASE_URL": settings.BASE_URL,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "nav_menu_items": nav_menu_items,
    }
