from django.conf import settings
import pytest
import redis
from adit.core.utils.redis_lru import redis_lru


@pytest.fixture
def redis_client():
    redis_url = settings.REDIS_URL[:-1] + "7"
    return redis.Redis.from_url(redis_url)


@pytest.mark.skip(reason="Needs a running Redis server.")
def test_lru_caches_successfully(redis_client):
    times_called = [0]

    @redis_lru()
    def func(x, y):
        times_called[0] += 1
        return x + y

    func.init(redis_client)

    result = func(1, 2)
    assert result == 3
    assert times_called == [1]

    result = func(1, 2)
    assert result == 3
    assert times_called == [1]

    (hits, misses, capacity, size) = func.info()

    assert hits == 1
    assert misses == 1
    assert capacity == 5000
    assert size == 1

    func.clear()


@pytest.mark.skip(reason="Needs a running Redis server.")
def test_lru_caches_successfully_with_slicer(redis_client):
    times_called = [0]

    @redis_lru(slicer=slice(2))
    def func(x, y, z):
        times_called[0] += 1
        return x + y + z

    func.init(redis_client)

    result = func(1, 2, 3)
    assert result == 6
    assert times_called == [1]

    # The third value is not considered the second time as
    # a slicer is used (two only check the first two values).
    result = func(1, 2, "z")
    assert result == 6
    assert times_called == [1]

    (hits, misses, capacity, size) = func.info()

    assert hits == 1
    assert misses == 1
    assert capacity == 5000
    assert size == 1

    func.clear()
