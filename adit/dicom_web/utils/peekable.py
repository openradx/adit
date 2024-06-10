from collections import deque
from typing import AsyncIterator, Deque, Optional, TypeVar

T = TypeVar("T")


class AsyncPeekable(AsyncIterator[T]):
    """Wrap an async iterator to allow lookahead elements.

    Call :meth:`peek` on the result to get the value that will be returned
    by :func:`__anext__`. This won't advance the iterator:

        >>> p = AsyncPeekable(['a', 'b'])
        >>> await p.peek()
        'a'
        >>> await p.__anext__()
        'a'

    Pass :meth:`peek` a default value to return that instead of raising
    ``StopAsyncIteration`` when the iterator is exhausted.

        >>> p = AsyncPeekable([])
        >>> await p.peek('hi')
        'hi'
    """

    def __init__(self, iterable: AsyncIterator[T]) -> None:
        self._it = iterable
        self._cache: Deque[T] = deque()

    def __aiter__(self) -> "AsyncPeekable":
        return self

    async def __anext__(self) -> T:
        if self._cache:
            return self._cache.popleft()

        return await self._it.__anext__()

    async def peek(self, default: Optional[T] = None) -> T:
        """Return the item that will be next returned from ``__anext__``.

        Return ``default`` if there are no items left. If ``default`` is not
        provided, raise ``StopAsyncIteration``.
        """
        if not self._cache:
            try:
                item = await self._it.__anext__()
                self._cache.append(item)
            except StopAsyncIteration:
                if default is None:
                    raise
                return default

        return self._cache[0]
