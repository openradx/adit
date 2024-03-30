from functools import wraps

from asgiref.sync import sync_to_async
from django.contrib.auth import get_user
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from .utils.auth_utils import is_logged_in_user


def login_required_async(view_func):
    @wraps(view_func)
    async def _wrapped_view(request, *args, **kwargs):
        user = await sync_to_async(get_user)(request)
        if not user.is_authenticated:
            path = request.build_absolute_uri()
            return redirect_to_login(path)

        return await view_func(request, *args, **kwargs)

    return _wrapped_view


def permission_required_async(permission_required: str | tuple[str]):
    def decorator(view_func):
        @wraps(view_func)
        async def _wrapped_view(request, *args, **kwargs):
            if not permission_required:
                raise ImproperlyConfigured

            if isinstance(permission_required, str):
                perms = (permission_required,)
            else:
                perms = permission_required

            user = await sync_to_async(get_user)(request)

            if is_logged_in_user(user) and user.has_perms(perms):
                return await view_func(request, *args, **kwargs)

            raise PermissionDenied

        return _wrapped_view

    return decorator
