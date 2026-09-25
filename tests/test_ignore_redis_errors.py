"""针对 ``ignore_redis_errors`` 选项的测试。

这些测试不依赖真实的 Redis 服务器：直接替换缓存实例的 ``get``/``put``/``aget``/``aput``，
在该边界抛出 :class:`redis.exceptions.RedisError`，从而验证 ``exec``/``aexec`` 的错误处置逻辑、
``Stats.err`` 计数，以及实例级与 ``decorate`` 级配置的优先级。
"""

from uuid import uuid4

import pytest
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ConnectionError as RedisConnectionError

from redis_func_cache import LruPolicy, RedisFuncCache


def _boom_sync(*args, **kwargs):
    raise RedisConnectionError("simulated redis connection error")


async def _boom_async(*args, **kwargs):
    raise RedisConnectionError("simulated redis connection error")


def _miss_sync(*args, **kwargs):
    return None


async def _miss_async(*args, **kwargs):
    return None


def make_sync_cache(**kwargs) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, LruPolicy, factory=Redis, **kwargs)


def make_async_cache(**kwargs) -> RedisFuncCache:
    return RedisFuncCache(uuid4().hex, LruPolicy, factory=AsyncRedis, **kwargs)


class TestSyncExec:
    """同步路径（``exec``）的错误处置。"""

    def test_read_error_raised_by_default(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_sync_cache()

        @cache
        def echo(x):
            return x

        monkeypatch.setattr(cache, "get", _boom_sync)
        with cache.stats_context() as stats, pytest.raises(RedisConnectionError):
            echo("v")

        assert stats.count == 1
        assert stats.read == 0
        assert stats.err == 1
        assert stats.exec == 0
        assert stats.write == 0

    def test_read_error_ignored_degrades_to_execution(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_sync_cache(ignore_redis_errors=True)
        calls = []

        @cache
        def echo(x):
            calls.append(x)
            return x

        # 读失败后降级为未命中；随后写也失败，同样被忽略
        monkeypatch.setattr(cache, "get", _boom_sync)
        monkeypatch.setattr(cache, "put", _boom_sync)
        with cache.stats_context() as stats:
            assert echo("v") == "v"

        assert calls == ["v"]
        assert stats.count == 1
        assert stats.err == 2
        assert stats.read == 0
        assert stats.write == 0
        assert stats.miss == 0
        assert stats.exec == 1

    def test_write_error_raised_by_default(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_sync_cache()

        @cache
        def echo(x):
            return x

        monkeypatch.setattr(cache, "get", _miss_sync)
        monkeypatch.setattr(cache, "put", _boom_sync)
        with cache.stats_context() as stats, pytest.raises(RedisConnectionError):
            echo("v")

        assert stats.read == 1
        assert stats.miss == 1
        assert stats.exec == 1
        assert stats.err == 1
        assert stats.write == 0

    def test_write_error_ignored_returns_result(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_sync_cache(ignore_redis_errors=True)

        @cache
        def echo(x):
            return x

        monkeypatch.setattr(cache, "get", _miss_sync)
        monkeypatch.setattr(cache, "put", _boom_sync)
        with cache.stats_context() as stats:
            assert echo("v") == "v"

        assert stats.read == 1
        assert stats.miss == 1
        assert stats.exec == 1
        assert stats.err == 1
        assert stats.write == 0

    def test_decorate_overrides_instance(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_sync_cache(ignore_redis_errors=True)

        @cache.decorate(ignore_redis_errors=False)
        def strict(x):
            return x

        @cache.decorate(ignore_redis_errors=True)
        def tolerant(x):
            return x

        monkeypatch.setattr(cache, "get", _boom_sync)
        with pytest.raises(RedisConnectionError):
            strict("v")
        assert tolerant("v") == "v"

    def test_direct_exec_falls_back_to_instance(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_sync_cache(ignore_redis_errors=True)

        def f(x):
            return x

        monkeypatch.setattr(cache, "get", _boom_sync)
        # 直接调用 exec 时，未显式传参则回退到实例级设置
        assert cache.exec(f, ("v",), {}) == "v"

        cache.ignore_redis_errors = False
        with pytest.raises(RedisConnectionError):
            cache.exec(f, ("v",), {})


class TestAsyncAexec:
    """异步路径（``aexec``）的错误处置。"""

    @pytest.mark.asyncio(loop_scope="function")
    async def test_read_error_raised_by_default(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_async_cache()

        @cache
        async def echo(x):
            return x

        monkeypatch.setattr(cache, "aget", _boom_async)
        with cache.stats_context() as stats, pytest.raises(RedisConnectionError):
            await echo("v")

        assert stats.count == 1
        assert stats.read == 0
        assert stats.err == 1
        assert stats.exec == 0
        assert stats.write == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_read_error_ignored_degrades_to_execution(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_async_cache(ignore_redis_errors=True)
        calls = []

        @cache
        async def echo(x):
            calls.append(x)
            return x

        # 读失败后降级为未命中；随后写也失败，同样被忽略
        monkeypatch.setattr(cache, "aget", _boom_async)
        monkeypatch.setattr(cache, "aput", _boom_async)
        with cache.stats_context() as stats:
            assert await echo("v") == "v"

        assert calls == ["v"]
        assert stats.count == 1
        assert stats.err == 2
        assert stats.read == 0
        assert stats.write == 0
        assert stats.miss == 0
        assert stats.exec == 1

    @pytest.mark.asyncio(loop_scope="function")
    async def test_write_error_raised_by_default(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_async_cache()

        @cache
        async def echo(x):
            return x

        monkeypatch.setattr(cache, "aget", _miss_async)
        monkeypatch.setattr(cache, "aput", _boom_async)
        with cache.stats_context() as stats, pytest.raises(RedisConnectionError):
            await echo("v")

        assert stats.read == 1
        assert stats.miss == 1
        assert stats.exec == 1
        assert stats.err == 1
        assert stats.write == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_write_error_ignored_returns_result(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_async_cache(ignore_redis_errors=True)

        @cache
        async def echo(x):
            return x

        monkeypatch.setattr(cache, "aget", _miss_async)
        monkeypatch.setattr(cache, "aput", _boom_async)
        with cache.stats_context() as stats:
            assert await echo("v") == "v"

        assert stats.read == 1
        assert stats.miss == 1
        assert stats.exec == 1
        assert stats.err == 1
        assert stats.write == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_decorate_overrides_instance(self, monkeypatch: pytest.MonkeyPatch):
        cache = make_async_cache(ignore_redis_errors=True)

        @cache.decorate(ignore_redis_errors=False)
        async def strict(x):
            return x

        @cache.decorate(ignore_redis_errors=True)
        async def tolerant(x):
            return x

        monkeypatch.setattr(cache, "aget", _boom_async)
        with pytest.raises(RedisConnectionError):
            await strict("v")
        assert await tolerant("v") == "v"
