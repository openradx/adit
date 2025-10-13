from typing import AsyncIterator

import pytest

from adit.dicom_web.utils.peekable import AsyncPeekable


@pytest.fixture
def mock_async_iterator():
    async def _mock_async_iterator() -> AsyncIterator[int]:
        yield 1
        yield 2
        yield 3

    return _mock_async_iterator


@pytest.mark.asyncio
async def test_peek(mock_async_iterator) -> None:
    peekable = AsyncPeekable(mock_async_iterator())
    assert await peekable.peek() == 1
    assert await peekable.peek() == 1
    assert await peekable.__anext__() == 1
    assert await peekable.peek() == 2


@pytest.mark.asyncio
async def test_default_value(mock_async_iterator) -> None:
    peekable = AsyncPeekable(mock_async_iterator())
    assert await peekable.peek(42) == 1
    assert await peekable.__anext__() == 1
    assert await peekable.peek(42) == 2
    assert await peekable.__anext__() == 2
    assert await peekable.peek(42) == 3
    assert await peekable.__anext__() == 3
    assert await peekable.peek(42) == 42


@pytest.mark.asyncio
async def test_empty(mock_async_iterator) -> None:
    peekable = AsyncPeekable(mock_async_iterator())
    assert await peekable.peek(42) == 1
    assert await peekable.__anext__() == 1
    assert await peekable.__anext__() == 2
    assert await peekable.peek(42) == 3
    assert await peekable.__anext__() == 3
    with pytest.raises(StopAsyncIteration):
        await peekable.peek()
    with pytest.raises(StopAsyncIteration):
        await peekable.__anext__()
