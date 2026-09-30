"""Constructor-level validation: key-fragment characters and client sync/async kind.

None of these tests need a live Redis server: every rejection happens before
the first command is issued.
"""

import asyncio
from collections.abc import Generator

import pytest
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from redis_func_cache import RedisFuncCache, lru_policy

BAD_FRAGMENTS = [
    "with-star*",
    "with-question?",
    "with-bracket[",
    "with-backslash\\",
    "with-open-brace{",
    "with-close-brace}",
]


@pytest.fixture
def sync_client() -> Generator[Redis]:
    client = Redis()
    yield client
    client.close()


@pytest.fixture
def async_client() -> Generator[AsyncRedis]:
    client = AsyncRedis()
    yield client
    # detach the lazy pool without touching the network; use a private loop so
    # the session-level current-loop state managed by conftest stays intact
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(client.connection_pool.disconnect())
    finally:
        loop.close()


@pytest.mark.parametrize("fragment", BAD_FRAGMENTS)
def test_prefix_rejects_glob_and_hash_tag_characters(sync_client, fragment):
    with pytest.raises(ValueError, match="glob or hash-tag"):
        RedisFuncCache(name="validation-test", policy=lru_policy, redis_client=sync_client, prefix=fragment)


@pytest.mark.parametrize("fragment", BAD_FRAGMENTS)
def test_name_rejects_glob_and_hash_tag_characters(sync_client, fragment):
    with pytest.raises(ValueError, match="glob or hash-tag"):
        RedisFuncCache(name=fragment, policy=lru_policy, redis_client=sync_client)


def test_prefix_and_name_accept_plain_fragments(sync_client):
    cache = RedisFuncCache(name="app-1", policy=lru_policy, redis_client=sync_client, prefix="rfc:")
    assert cache.prefix == "rfc:"
    assert cache.name == "app-1"


def test_sync_decorated_function_rejects_async_client(async_client):
    cache = RedisFuncCache("validation-test", lru_policy, redis_client=async_client)

    @cache
    def echo(x):
        return x

    with pytest.raises(TypeError, match="synchronous redis client"):
        echo(1)


@pytest.mark.asyncio(loop_scope="function")
async def test_async_decorated_function_rejects_sync_client(sync_client):
    cache = RedisFuncCache("validation-test", lru_policy, redis_client=sync_client)

    @cache
    async def aecho(x):
        return x

    with pytest.raises(TypeError, match="asynchronous redis client"):
        await aecho(1)


def test_purge_rejects_wrong_client_kind(async_client):
    cache = RedisFuncCache("validation-test", lru_policy, redis_client=async_client)
    with pytest.raises(TypeError, match="synchronous"):
        cache.purge(redis_client=async_client)


@pytest.mark.asyncio(loop_scope="function")
async def test_apurge_rejects_wrong_client_kind(sync_client):
    cache = RedisFuncCache("validation-test", lru_policy, redis_client=sync_client)
    with pytest.raises(TypeError, match="asynchronous"):
        await cache.apurge(redis_client=sync_client)


def test_get_size_rejects_wrong_client_kind(async_client):
    cache = RedisFuncCache("validation-test", lru_policy, redis_client=async_client)
    with pytest.raises(TypeError, match="synchronous"):
        cache.get_size(redis_client=async_client)


def test_vacuum_rejects_wrong_client_kind(async_client):
    cache = RedisFuncCache("validation-test", lru_policy, redis_client=async_client)
    with pytest.raises(TypeError, match="synchronous"):
        cache.vacuum(redis_client=async_client)
