from typing import cast

from django.contrib.auth.models import Group
from django.http import HttpRequest

from adit_radis_shared.accounts.models import User


class ActiveGroupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if request.user.is_authenticated:
            user = cast(User, request.user)

            # A stuff user can have any group as active
            if user.is_staff and not user.active_group:
                group = user.groups.first()
                if not group:
                    group = Group.objects.first()
                user.active_group = group
                user.save()

            # A normal user can only have one of his groups active
            elif not user.active_group or not user.groups.filter(pk=user.active_group.pk).exists():
                group = user.groups.first()
                user.active_group = group
                user.save()

        return self.get_response(request)
