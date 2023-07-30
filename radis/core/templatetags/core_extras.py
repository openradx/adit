import re

from django.template import Library

register = Library()


# TODO: Resolve reference names from another source in the context
# Context must be set in the view
@register.simple_tag(takes_context=True)
def url_abbreviation(context: dict, url: str):
    abbr = re.sub(r"^(https?://)?(www.)?", "", url)
    return abbr[:5]
