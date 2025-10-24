import asyncio

import pytest
from pydicom import Dataset

from adit.dicom_web.utils import wadors_utils


@pytest.mark.asyncio
async def test_wado_retrieve_integration(monkeypatch):
    datasets = []
    for index in range(3):
        ds = Dataset()
        ds.PatientID = "P123"
        ds.StudyInstanceUID = "1.2.840.113845.11.1000000001951524609.20200705182951.2689481"
        ds.SeriesInstanceUID = f"1{index}"
        ds.SOPInstanceUID = f"2{index}"
        datasets.append(ds)
    created_operators = []

    class FakeDicomServer:
        def __init__(
            self,
            *,
            name: str,
            ae_title: str,
            host: str,
            port: int,
            dicomweb_wado_support: bool = True,
            dicomweb_root_url: str = "http://example.com",
        ) -> None:
            self.name = name
            self.ae_title = ae_title
            self.host = host
            self.port = port
            self.dicomweb_wado_support = dicomweb_wado_support
            self.dicomweb_root_url = dicomweb_root_url
            self.patient_root_find_support = False
            self.patient_root_get_support = False
            self.patient_root_move_support = False
            self.study_root_find_support = False
            self.study_root_get_support = False
            self.study_root_move_support = False
            self.store_scp_support = False

    class FakeDicomOperator:
        def __init__(self, server):
            self.server = server
            self.fetch_study_calls: list[tuple[str, str]] = []
            created_operators.append(self)

        def fetch_study(self, *, patient_id: str, study_uid: str, callback):
            self.fetch_study_calls.append((patient_id, study_uid))
            for ds in datasets:
                callback(ds)

        def fetch_series(self, *args, **kwargs):  # pragma: no cover - not used in this test
            raise AssertionError("fetch_series should not be called in study level test")

        def fetch_image(self, *args, **kwargs):  # pragma: no cover - not used in this test
            raise AssertionError("fetch_image should not be called in study level test")

    manipulator_calls: list[Dataset] = []

    class FakeDicomManipulator:
        def manipulate(
            self,
            ds: Dataset,
            pseudonym,
            trial_protocol_id,
            trial_protocol_name,
        ) -> None:
            manipulator_calls.append(ds)

    def immediate_sync_to_async(func, *, thread_sensitive=False):
        async def wrapper(*args, **kwargs):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

        return wrapper

    monkeypatch.setattr(wadors_utils, "DicomServer", FakeDicomServer)
    monkeypatch.setattr(wadors_utils, "DicomOperator", FakeDicomOperator)
    monkeypatch.setattr(wadors_utils, "DicomManipulator", FakeDicomManipulator)
    monkeypatch.setattr(wadors_utils, "sync_to_async", immediate_sync_to_async)
    query = {
        "PatientID": "P123",
        "StudyInstanceUID": "1.2.840.113845.11.1000000001951524609.20200705182951.2689481",
    }
    server = wadors_utils.DicomServer(
        name="Test Server",
        ae_title="TEST",
        host="localhost",
        port=104,
    )
    retrieved_datasets = []
    async for dataset in wadors_utils.wado_retrieve(server, query, "STUDY"):
        retrieved_datasets.append(dataset)
    assert retrieved_datasets == datasets
    assert manipulator_calls == datasets
    assert created_operators[0].fetch_study_calls == [
        ("P123", "1.2.840.113845.11.1000000001951524609.20200705182951.2689481")
    ]


'''
Mock tests simulating the race condition in the old implementation and 
how adding a sentinel resolves it. Can be removed if deemed unnecessary.

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
            done, _ = await asyncio.wait(
                [fetch_task, queue_get_task], return_when=asyncio.FIRST_COMPLETED
            )

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


@pytest.mark.asyncio
async def test_sentinel_prevents_race_condition():
    """Test that the sentinel pattern ensures all items are processed."""
    results = []

    async def wado_retrieve_with_sentinel():
        queue = asyncio.Queue()

        async def fetch():
            for i in range(3):
                await asyncio.sleep(0.0001)
                queue.put_nowait(i)

        fetch_task = asyncio.create_task(fetch())

        async def add_sentinel_when_done():
            await fetch_task
            await queue.put(None)

        asyncio.create_task(add_sentinel_when_done())

        while True:
            item = await queue.get()
            if item is None:
                break
            results.append(item)
            await asyncio.sleep(0.0003)  # Simulate delay

    await wado_retrieve_with_sentinel()

    assert results == [0, 1, 2]  # All items should be retrieved
'''
