from urllib.parse import urlencode
from django.template import Library

register = Library()

@register.simple_tag
def append_xnat_query(
    url,
    xnat_project_id=None,
    experiment_id=None,
):
    params = {}
    if xnat_project_id:
        params["xnat_project_id"] = xnat_project_id
    if experiment_id:
        params["experiment_id"] = experiment_id

    
    if params:
        if "?" in url:
            return "%s&%s" % (url, urlencode(params))
        else:
            return "%s?%s" % (url, urlencode(params))

    return url
