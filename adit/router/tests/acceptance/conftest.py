import os

# The worker runs in a thread next to Django's sync test code.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
