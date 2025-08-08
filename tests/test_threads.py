from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool
from threading import Barrier, Thread

import pytest

from ._catches import CACHES


def echo(x):
    return x


@pytest.fixture(autouse=True)
def clean_caches():
    """自动清理缓存的夹具，在每个测试前后运行。"""
    # 测试前清理
    for cache in CACHES.values():
        cache.policy.purge()
    yield
    # 测试后清理
    for cache in CACHES.values():
        cache.policy.purge()


def test_two_threads():
    """测试两个线程并发访问缓存，结果正确且无竞态。"""
    for cache in CACHES.values():
        results = {}
        _echo = cache.decorate(echo)
        bar = Barrier(2)

        def f(n, x):
            bar.wait()
            v = _echo(x)
            results[n] = v

        t1 = Thread(target=f, args=(1, 1))
        t2 = Thread(target=f, args=(2, 2))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results == {1: 1, 2: 2}


def test_pool_map():
    """测试线程池并发 map 缓存装饰器，结果正确。"""
    for cache in CACHES.values():
        _echo = cache.decorate(echo)
        with ThreadPool(processes=cpu_count()) as pool:
            result = pool.map(_echo, range(cache.maxsize * 2))
        assert result == list(range(cache.maxsize * 2))


def test_high_concurrency():
    """高并发下多线程访问同一 key 和不同 key，确保无异常且缓存一致。"""
    for cache in CACHES.values():
        _echo = cache.decorate(echo)
        results = []
        N = 20
        threads = []
        # 同一 key
        for _ in range(N):
            t = Thread(target=lambda: results.append(_echo(42)))
            threads.append(t)
        # 不同 key
        for i in range(N):
            t = Thread(target=lambda i=i: results.append(_echo(i)))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 检查所有结果都正确
        assert 42 in results
        for i in range(N):
            assert i in results


def test_concurrent_exception():
    """多线程下被缓存函数抛异常时，所有线程都能收到异常。"""
    for cache in CACHES.values():

        def fail(x):
            raise ValueError("fail")

        _fail = cache.decorate(fail)
        errors = []

        def f():
            try:
                _fail(1)
            except Exception as e:
                errors.append(e)

        threads = [Thread(target=f) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 5
