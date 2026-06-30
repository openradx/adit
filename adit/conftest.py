import nest_asyncio2
import pytest

pytest_plugins = ["adit_radis_shared.pytest_fixtures"]


def pytest_configure():
    # pytest-asyncio doesn't play well with pytest-playwright as
    # pytest-playwright creates an event loop for the whole test suite and
    # pytest-asyncio can't create an additional one then.
    # nest_asyncio2 works around this by allowing to create nested loops.
    # https://github.com/pytest-dev/pytest-asyncio/issues/543
    # https://github.com/microsoft/playwright-pytest/issues/167
    nest_asyncio2.apply()


@pytest.fixture(autouse=True)
def _reapply_nest_asyncio():
    # pytest-asyncio installs its own event loop (policy) per async test, which
    # undoes the nest_asyncio2 patch applied once in pytest_configure. Re-apply it
    # for every test so the loop that's current when an acceptance test calls
    # run_worker_once() (a nested run_until_complete on the running channels loop)
    # is always patched. Without this, the channels_live_server acceptance tests
    # fail with "This event loop is already running" once async tests have run.
    nest_asyncio2.apply()
