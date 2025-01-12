import sys
from typing import Callable, TypeVar, Union

if sys.version_info < (3, 10):  # pragma: no cover
    from typing_extensions import TypeGuard
else:  # pragma: no cover
    from typing import TypeGuard

import redis.asyncio.client
import redis.asyncio.cluster
import redis.client
import redis.cluster
import redis.commands.core

CallableTV = TypeVar("CallableTV", bound=Callable)

RedisSyncClientTypes = redis.client.Redis, redis.cluster.RedisCluster
RedisSyncClientT = Union[redis.client.Redis, redis.cluster.RedisCluster]
RedisAsyncClientTypes = redis.asyncio.client.Redis, redis.asyncio.cluster.RedisCluster
RedisAsyncClientT = Union[redis.asyncio.client.Redis, redis.asyncio.cluster.RedisCluster]
RedisClientTypes = (
    redis.client.Redis,
    redis.cluster.RedisCluster,
    redis.asyncio.client.Redis,
    redis.asyncio.cluster.RedisCluster,
)
RedisClientT = Union[
    redis.client.Redis, redis.asyncio.client.Redis, redis.cluster.RedisCluster, redis.asyncio.cluster.RedisCluster
]
RedisClientTV = TypeVar("RedisClientTV", bound=RedisClientT)


def is_async_redis_client(client: RedisClientT) -> TypeGuard[RedisAsyncClientT]:
    """
    Returns True if the given Redis client is an asynchronous client.
    """
    return isinstance(client, RedisAsyncClientTypes)


def is_sync_redis_client(client: RedisClientT) -> TypeGuard[RedisSyncClientT]:
    """
    Returns True if the given Redis client is a synchronous client.
    """
    return isinstance(client, RedisSyncClientTypes)
