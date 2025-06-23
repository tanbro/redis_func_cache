from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Callable, Literal, TypeVar, Union

if sys.version_info < (3, 10):  # pragma: no cover
    from typing_extensions import TypeGuard
else:  # pragma: no cover
    from typing import TypeGuard

if TYPE_CHECKING:  # pragma: no cover
    from typing import Protocol

    if sys.version_info < (3, 11):  # pragma: no cover
        from typing_extensions import Self
    else:
        from typing import Self

    from _typeshed import ReadableBuffer

import redis.asyncio.client
import redis.asyncio.cluster
import redis.client
import redis.cluster

CallableTV = TypeVar("CallableTV", bound=Callable)

RedisSyncClientTypes = redis.client.Redis, redis.cluster.RedisCluster
RedisSyncClientT = Union[redis.client.Redis, redis.cluster.RedisCluster]
RedisAsyncClientTypes = redis.asyncio.client.Redis, redis.asyncio.cluster.RedisCluster
RedisAsyncClientT = Union[redis.asyncio.client.Redis, redis.asyncio.cluster.RedisCluster]
RedisClusterClientTypes = redis.cluster.RedisCluster, redis.asyncio.cluster.RedisCluster
RedisClusterClientT = Union[redis.cluster.RedisCluster, redis.asyncio.cluster.RedisCluster]
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


SerializerName = Literal["json", "pickle", "bson", "msgpack", "yaml", "cbor", "cloudpickle"]


if TYPE_CHECKING:  # pragma: no cover

    class Hash(Protocol):
        def update(self, data: ReadableBuffer, /) -> None: ...
        def digest(self) -> bytes: ...
        def hexdigest(self) -> str: ...
        def copy(self) -> Self: ...


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


def is_redis_cluster_client(client: RedisClientT) -> TypeGuard[RedisClusterClientT]:
    """
    Returns True if the given Redis client is a cluster client.
    """
    return isinstance(client, RedisClusterClientTypes)
