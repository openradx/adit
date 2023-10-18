from functools import reduce

from django.db.models import Model

from radis.accounts.models import User


def deepgetattr(obj: object, attr: str) -> object:
    """Recurses through an attribute chain to get the ultimate value."""
    return reduce(getattr, attr.split("."), obj)


def is_object_owner(obj: Model, user: User, accessor: str = "owner") -> bool:
    if not user.is_authenticated:
        raise AssertionError("The user must be authenticated to check if he is the owner.")

    if user.is_superuser or user.is_staff:
        return True

    return user == deepgetattr(obj, accessor)
