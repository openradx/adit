from typing import TypeGuard

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from adit.accounts.models import User


def is_logged_in_user(user: AbstractBaseUser | AnonymousUser) -> TypeGuard[User]:
    return user.is_authenticated and not user.is_anonymous


def is_staff_user(user: AbstractBaseUser | AnonymousUser) -> TypeGuard[User]:
    return is_logged_in_user(user) and user.is_staff


def is_superuser(user: AbstractBaseUser | AnonymousUser) -> TypeGuard[User]:
    return is_logged_in_user(user) and user.is_superuser
