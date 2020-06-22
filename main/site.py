nav_menu_items = []
job_detail_url_names = {}
job_type_choices = []


def register_main_menu_item(url_name, label):
    nav_menu_items.append({
        'url_name': url_name,
        'label': label
    })

def register_dicom_job(type_key, type_name, detail_url_name):
    if type_key in job_detail_url_names:
        raise KeyError(f'The key {type_key} for job type {type_name} is already registered.')

    job_detail_url_names[type_key] = detail_url_name
    job_type_choices.append((type_key, type_name))

def inject_context(request):
    return {'nav_menu_items': nav_menu_items}
