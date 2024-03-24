from typing import cast

from django.http import HttpRequest

from adit_radis_shared.accounts.models import User


class ActiveGroupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if request.user.is_authenticated:
            user = cast(User, request.user)

            # Make sure a logged in user has an active group if he is assigned to any
            if not user.active_group or not user.groups.filter(pk=user.active_group.pk).exists():
                group = user.groups.first()
                user.active_group = group
                user.save()

        return self.get_response(request)
