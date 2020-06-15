nav_menu_items = []
transfer_job_type_choices = []

def register_main_menu_item(url_name, label):
    nav_menu_items.append({
        'url_name': url_name,
        'label': label
    })

def register_transfer_job_type(key, name):
    transfer_job_type_choices.append((key, name))

def inject_context(request):
    return {'nav_menu_items': nav_menu_items}
