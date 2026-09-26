import asyncio
from random import randint

import pytest
import pytest_asyncio

from ._catches import ASYNC_CACHES, ASYNC_MULTI_CACHES, CACHES
from ._mocks import patch_object


def _echo(x):
    return x


@pytest_asyncio.fixture(autouse=True)
async def clean_async_caches():
    """自动清理异步缓存的夹具，在每个测试前后运行。"""
    # 测试前清理
    coros = (cache.policy.apurge(redis_client=cache.get_redis_client()) for cache in ASYNC_CACHES.values())
    await asyncio.gather(*coros)
    coros = (cache.policy.apurge(redis_client=cache.get_redis_client()) for cache in ASYNC_MULTI_CACHES.values())
    await asyncio.gather(*coros)
    yield
    # 测试后清理
    try:
        coros = (cache.policy.apurge(redis_client=cache.get_redis_client()) for cache in ASYNC_CACHES.values())
        await asyncio.gather(*coros)
        coros = (cache.policy.apurge(redis_client=cache.get_redis_client()) for cache in ASYNC_MULTI_CACHES.values())
        await asyncio.gather(*coros)
    except RuntimeError:
        # 如果事件循环已关闭，忽略错误
        pass


@pytest.mark.asyncio(loop_scope="function")
async def test_async_staticmethod_descriptor():
    cache = ASYNC_CACHES["lru"]

    class Example:
        @cache
        @staticmethod
        async def echo(value):
            await asyncio.sleep(0)
            return value

    async def execute(user_function, user_args, user_kwds, *args, **kwargs):
        return await user_function(*user_args, **user_kwds)

    with patch_object(cache, "aexec", side_effect=execute):
        assert isinstance(Example.__dict__["echo"], staticmethod)
        assert await Example.echo(1) == 1
        assert await Example().echo(2) == 2


@pytest.mark.asyncio(loop_scope="function")
async def test_async_classmethod_decorator_order():
    cache = ASYNC_CACHES["lru"]

    class Example:
        @classmethod
        @cache(excludes_positional=[0])
        async def echo(cls, value):
            await asyncio.sleep(0)
            return value

    async def execute(user_function, user_args, user_kwds, *args, **kwargs):
        return await user_function(*user_args, **user_kwds)

    with patch_object(cache, "aexec", side_effect=execute):
        assert await Example.echo(1) == 1
        assert await Example().echo(2) == 2


@pytest.mark.asyncio(loop_scope="function")
async def test_async_simple():
    for cache in ASYNC_CACHES.values():

        @cache
        async def echo(x):
            await asyncio.sleep(0)
            return _echo(x)

        n = randint(cache.maxsize + 1, 2 * cache.maxsize)
        for i in range(n):
            assert i == await echo(i)
            assert i == await echo(i)

        assert cache.maxsize == await cache.policy.aget_size(redis_client=cache.get_redis_client())


@pytest.mark.asyncio(loop_scope="function")
async def test_async_multi_simple():
    for cache in ASYNC_MULTI_CACHES.values():

        @cache
        async def echo1(x):
            await asyncio.sleep(0)
            return _echo(x)

        @cache
        async def echo2(x):
            await asyncio.sleep(0)
            return _echo(x)

        n = randint(cache.maxsize + 1, 2 * cache.maxsize)
        for i in range(n):
            assert i == await echo1(i)
            assert i == await echo2(i)
            assert i == await echo1(i)
            assert i == await echo2(i)


@pytest.mark.asyncio(loop_scope="function")
async def test_async_multi_missing():
    for cache in ASYNC_MULTI_CACHES.values():

        @cache
        async def echo1(x):
            await asyncio.sleep(0)
            return _echo(x)

        @cache
        async def echo2(x):
            await asyncio.sleep(0)
            return _echo(x)

        n = randint(cache.maxsize // 2 + 1, cache.maxsize + 1)
        for i in range(n):
            with patch_object(cache, "aget", return_value=cache.serialize(i)) as mock_get:  # noqa: SIM117
                with patch_object(cache, "aput") as mock_put:
                    await echo1(i)
                    mock_get.assert_called_once()
                    mock_put.assert_not_called()
            with patch_object(cache, "aget", return_value=cache.serialize(i)) as mock_get:  # noqa: SIM117
                with patch_object(cache, "aput") as mock_put:
                    await echo2(i)
                    mock_get.assert_called_once()
                    mock_put.assert_not_called()


def test_async_for_sync_type_error():
    for cache in ASYNC_CACHES.values():

        @cache
        def fn(x):
            return x

        with pytest.raises(TypeError):
            fn(1)


@pytest.mark.asyncio(loop_scope="function")
async def test_sync_for_async_type_error():
    for cache in CACHES.values():

        @cache
        async def fn(x):
            await asyncio.sleep(0)
            return x

        with pytest.raises(TypeError):
            await fn(1)
