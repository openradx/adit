import re


def sanitize_filename(name):
    """Windows can't handle some file and folder names so we have to sanitize them."""
    sanitized_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    sanitized_name = sanitized_name.strip()
    if not sanitized_name:
        sanitized_name = "default"
    return sanitized_name
