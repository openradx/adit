from django.conf import settings

nav_menu_items = []


def register_main_menu_item(url_name, label):
    nav_menu_items.append({"url_name": url_name, "label": label})


def base_context_processor(request):
    return {
        "BASE_URL": settings.BASE_URL,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "nav_menu_items": nav_menu_items,
    }
