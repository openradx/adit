from django.test import TestCase
from django.conf import settings
import redis
from adit.main.utils.redis_lru import redis_lru


class RedisLruTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        redis_url = settings.REDIS_URL[:-1] + "7"
        cls.redis_client = redis.Redis.from_url(redis_url)

    def test_lru_caches_successfully(self):
        times_called = [0]

        @redis_lru()
        def func(x, y):
            times_called[0] += 1
            return x + y

        func.init(self.redis_client)

        result = func(1, 2)
        self.assertEqual(result, 3)
        self.assertEqual(times_called, [1])

        result = func(1, 2)
        self.assertEqual(result, 3)
        self.assertEqual(times_called, [1])

        (hits, misses, capacity, size) = func.info()

        self.assertEqual(hits, 1)
        self.assertEqual(misses, 1)
        self.assertEqual(capacity, 5000)
        self.assertEqual(size, 1)

        func.clear()

    def test_lru_caches_successfully_with_slicer(self):
        times_called = [0]

        @redis_lru(slicer=slice(2))
        def func(x, y, z):
            times_called[0] += 1
            return x + y + z

        func.init(self.redis_client)

        result = func(1, 2, 3)
        self.assertEqual(result, 6)
        self.assertEqual(times_called, [1])

        # The third value is not considered the second time as
        # a slicer is used (two only check the first two values).
        result = func(1, 2, "z")
        self.assertEqual(result, 6)
        self.assertEqual(times_called, [1])

        (hits, misses, capacity, size) = func.info()

        self.assertEqual(hits, 1)
        self.assertEqual(misses, 1)
        self.assertEqual(capacity, 5000)
        self.assertEqual(size, 1)

        func.clear()
