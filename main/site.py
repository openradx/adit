nav_menu_items = []
transfer_job_type_choices = []
#job_detail_paths = []

def register_main_menu_item(url_name, label):
    nav_menu_items.append({
        'url_name': url_name,
        'label': label
    })

# TODO
#def register_transfer_job(job_type_key, job_type_name, job_detail_path):


def register_transfer_job_type(key, name):
    transfer_job_type_choices.append((key, name))

def inject_context(request):
    return {'nav_menu_items': nav_menu_items}
