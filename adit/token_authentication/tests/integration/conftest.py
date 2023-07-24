import os

# Workaround to make playwright work with Django
# see https://github.com/microsoft/playwright-pytest/issues/29#issuecomment-731515676
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
