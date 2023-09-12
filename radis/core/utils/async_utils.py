import asyncio
from typing import AsyncIterator


def iter_over_async(ait: AsyncIterator, loop: asyncio.AbstractEventLoop):
    ait = ait.__aiter__()

    async def get_next():
        try:
            obj = await ait.__anext__()
            return False, obj
        except StopAsyncIteration:
            return True, None

    while True:
        done, obj = loop.run_until_complete(get_next())
        if done:
            break
        yield obj
