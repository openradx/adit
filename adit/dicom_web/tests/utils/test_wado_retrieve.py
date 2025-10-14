import asyncio

import pytest


@pytest.mark.asyncio
async def test_race_condition():
    results = []

    async def wado_retrieve_rc():
        queue = asyncio.Queue()

        async def fetch():
            for i in range(3):
                # simulate fetch_study that takes some time, allowing queue_get_task to run
                await asyncio.sleep(0.0001)
                queue.put_nowait(i)

        fetch_task = asyncio.create_task(fetch())

        while True:
            queue_get_task = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait([fetch_task, queue_get_task],
                                         return_when=asyncio.FIRST_COMPLETED)

            finished = False
            for task in done:
                if task == queue_get_task:
                    results.append(queue_get_task.result())
                    # artificial delay after queue_get_task, allowing fetch_task to finish 
                    # before the final queue_get_task can run
                    await asyncio.sleep(0.0003)
                if task == fetch_task:
                    finished = True

            if finished:
                queue_get_task.cancel()
                break

    await wado_retrieve_rc()
    
    assert results == [0, 1]
    # assert results in ([0, 1, 2], [0, 1], [0])

