from typing import TYPE_CHECKING, Type, TypeVar

T = TypeVar("T")


def with_type_hint(baseclass: Type[T]) -> Type[T]:
    """
    Useful function to make mixins with type hints
    """
    if TYPE_CHECKING:
        return baseclass

    return object
