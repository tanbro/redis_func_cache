from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool
from os import getenv
from threading import Barrier, Thread
from unittest import TestCase

from redis import Redis

from redis_func_cache import FifoPolicy, LfuPolicy, LruPolicy, LruTPolicy, MruPolicy, RedisFuncCache, RrPolicy

REDIS_URL = getenv("REDIS_URL", "redis://")
REDIS_FACTORY = lambda: Redis.from_url(REDIS_URL)  # noqa: E731
MAXSIZE = 8
CACHES = {
    "tlru": RedisFuncCache(__name__, LruTPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lru": RedisFuncCache(__name__, LruPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "mru": RedisFuncCache(__name__, MruPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "rr": RedisFuncCache(__name__, RrPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "fifo": RedisFuncCache(__name__, FifoPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
    "lfu": RedisFuncCache(__name__, LfuPolicy, client=REDIS_FACTORY, maxsize=MAXSIZE),
}


def echo(x):
    return x


class BasicTest(TestCase):
    def setUp(self):
        for cache in CACHES.values():
            cache.policy.purge()

    def test_two_threads(self):
        for cache in CACHES.values():
            results = {}

            _echo = cache.decorate(echo)
            bar = Barrier(2)

            def f(n, x):
                bar.wait()
                results[n] = _echo(x)

            t1 = Thread(target=f, args=(1, 1))
            t2 = Thread(target=f, args=(2, 2))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            self.assertDictEqual(results, {1: 1, 2: 2})

    def test_pool_map(self):
        for cache in CACHES.values():
            _echo = cache.decorate(echo)

            with ThreadPool(processes=cpu_count()) as pool:
                result = pool.map(_echo, range(cache.maxsize * 2))
            self.assertEqual(result, list(range(cache.maxsize * 2)))
