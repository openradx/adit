nav_menu_items = []
transfer_job_type_choices = []

def register_main_menu_item(name, label, url):
    nav_menu_items.append({
        'name': name,
        'label': label,
        'url': url
    })

def register_transfer_job_type(key, name):
    transfer_job_type_choices.append((key, name))

def inject_context(request):
    return {'nav_menu_items': nav_menu_items}
