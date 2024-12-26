from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool
from threading import Barrier, Thread
from unittest import TestCase

from ._catches import CACHES


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
