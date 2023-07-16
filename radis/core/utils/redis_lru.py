import pickle
from functools import wraps

from redis import Redis


def redis_lru(capacity=5000, slicer=slice(None)):
    """
    Simple Redis-based LRU cache decorator *.
    *conn*      Redis connection
    *capacity*  maximum number of entries in LRU cache
    *slicer*    slice object for restricting prototype args

    Usage is as simple as prepending the decorator to a function,
    passing a Redis connection object, and the desired capacity
    of your cache.

    @redis_lru(capacity=10000)
    def func(foo, bar):
        # some expensive operation
        return baz

    func.init(redis.StrictRedis())

    Uses 4 Redis keys, all suffixed with the function name:
        lru:keys: - sorted set, stores hash keys
        lru:vals: - hash, stores function output values
        lru:hits: - string, stores hit counter
        lru:miss: - string, stores miss counter

    * Functions prototypes must be serializable equivalent!

    Adapted from https://gist.github.com/kwarrick/4247343
    """

    def decorator(func):
        cache_keys = f"lru:keys:{func.__name__}"
        cache_vals = f"lru:vals:{func.__name__}"
        cache_hits = f"lru:hits:{func.__name__}"
        cache_miss = f"lru:miss:{func.__name__}"

        lvars: list[Redis]  # closure mutable

        def add(key, value):
            eject()
            nonlocal lvars
            conn: Redis = lvars[0]
            conn.incr(cache_miss)
            conn.hset(cache_vals, key, pickle.dumps(value))
            conn.zadd(cache_keys, {key: 0})
            return value

        def get(key):
            nonlocal lvars
            conn: Redis = lvars[0]
            value = conn.hget(cache_vals, key)
            if value:
                conn.incr(cache_hits)
                conn.zincrby(cache_keys, 1, key)
                value = pickle.loads(value)
            return value

        def eject():
            nonlocal lvars
            conn: Redis = lvars[0]
            count = int(min((capacity / 10) or 1, 1000))
            if conn.zcard(cache_keys) >= capacity:
                eject = conn.zrange(cache_keys, 0, count)
                conn.zremrangebyrank(cache_keys, 0, count)
                conn.hdel(cache_vals, *eject)

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal lvars
            conn = lvars[0]
            if conn:
                items = args + tuple(sorted(kwargs.items()))
                key = pickle.dumps(items[slicer])
                return get(key) or add(key, func(*args, **kwargs))

            return func(*args, **kwargs)

        def info():
            nonlocal lvars
            conn: Redis = lvars[0]
            size = int(conn.zcard(cache_keys) or 0)
            hits, misses = int(conn.get(cache_hits) or 0), int(conn.get(cache_miss) or 0)
            return hits, misses, capacity, size

        def clear():
            nonlocal lvars
            conn: Redis = lvars[0]
            conn.delete(cache_keys, cache_vals)
            conn.delete(cache_hits, cache_miss)

        def init(conn: Redis):
            nonlocal lvars
            lvars = [conn]

        # TODO: improve typing (not monkey patching)
        wrapper.init = init  # type: ignore
        wrapper.info = info  # type: ignore
        wrapper.clear = clear  # type: ignore
        return wrapper

    return decorator
