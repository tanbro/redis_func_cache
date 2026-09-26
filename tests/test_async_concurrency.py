"""异步并发测试（asyncio.gather）。

同步侧的线程并发见 test_threads.py；本文件覆盖协程并发下的正确性、
maxsize 约束、异常传播，并钉住文档声明的已知限制：cache stampede
（并发未命中没有 single-flight，同键在场的协程会各自执行函数）。
"""

import asyncio

import pytest
import pytest_asyncio

from ._catches import ASYNC_CACHES


@pytest_asyncio.fixture(autouse=True)
async def clean_async_caches():
    """自动清理异步缓存的夹具，在每个测试前后运行。"""
    coros = (cache.policy.apurge(cache.get_redis_client()) for cache in ASYNC_CACHES.values())
    await asyncio.gather(*coros)
    yield
    try:
        coros = (cache.policy.apurge(cache.get_redis_client()) for cache in ASYNC_CACHES.values())
        await asyncio.gather(*coros)
    except RuntimeError:
        pass


@pytest.mark.asyncio(loop_scope="function")
async def test_gather_same_key():
    """并发协程访问同一键：结果全部正确。"""
    for cache in ASYNC_CACHES.values():

        @cache
        async def echo(x):
            await asyncio.sleep(0)
            return x

        results = await asyncio.gather(*(echo(42) for _ in range(20)))
        assert results == [42] * 20


@pytest.mark.asyncio(loop_scope="function")
async def test_gather_distinct_keys():
    """并发协程访问不同键：结果正确，条目数不超过 maxsize（原子脚本约束）。"""
    for cache in ASYNC_CACHES.values():

        @cache
        async def echo(x):
            await asyncio.sleep(0)
            return x

        n = cache.maxsize * 2
        results = await asyncio.gather(*(echo(i) for i in range(n)))
        assert results == list(range(n))
        assert await cache.policy.aget_size(cache.get_redis_client()) <= cache.maxsize


@pytest.mark.asyncio(loop_scope="function")
async def test_concurrent_stampede_all_miss():
    """钉住已知限制（文档声明）：同键并发未命中没有 single-flight。

    用事件把所有协程拦在函数体内：它们都在任一 put 之前完成了 aget miss，
    因此函数执行次数等于并发数（cache stampede）。若未来实现 single-flight，
    此断言会失败——那正是改变行为时的提醒。
    """
    for cache in ASYNC_CACHES.values():
        await _stampede_all_miss(cache)


async def _stampede_all_miss(cache):
    """单缓存的 stampede 场景：所有协程越过 aget miss 后才统一放行。"""
    counter = [0]
    release = asyncio.Event()

    async def echo(x):
        counter[0] += 1
        await release.wait()
        return x

    echo = cache.decorate(echo)

    task = asyncio.gather(*(echo(1) for _ in range(5)))
    while counter[0] < 5:  # 让 5 个协程全部越过 aget miss、进入函数体
        await asyncio.sleep(0)
    release.set()

    assert await task == [1] * 5
    assert counter[0] == 5  # 全部在场协程各自执行
    assert await cache.policy.aget_size(cache.get_redis_client()) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_gather_exception():
    """并发协程下被缓存函数抛异常：每个协程都收到异常，且不留缓存条目。"""
    for cache in ASYNC_CACHES.values():

        @cache
        async def fail(x):
            raise ValueError(x)

        results = await asyncio.gather(*(fail(i) for i in range(5)), return_exceptions=True)
        assert all(isinstance(r, ValueError) for r in results)
        assert await cache.policy.aget_size(cache.get_redis_client()) == 0
