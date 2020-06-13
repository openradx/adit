nav_menu_items = []

def register_main_menu_item(name, label, url):
    nav_menu_items.append({
        'name': name,
        'label': label,
        'url': url
    })

def inject_context(request):
    return {'nav_menu_items': nav_menu_items}
