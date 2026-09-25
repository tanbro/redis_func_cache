from __future__ import annotations

from collections.abc import Callable
from inspect import ismodule
from types import ModuleType
from typing import Any, Literal, TypeGuard, TypeVar

import redis.asyncio.client
import redis.asyncio.cluster
import redis.client
import redis.cluster
import redis.commands.core

CallableTV = TypeVar("CallableTV", bound=Callable)

RedisSyncClientTypes = redis.client.Redis, redis.cluster.RedisCluster
RedisSyncClientT = redis.client.Redis | redis.cluster.RedisCluster
RedisAsyncClientTypes = redis.asyncio.client.Redis, redis.asyncio.cluster.RedisCluster
RedisAsyncClientT = redis.asyncio.client.Redis | redis.asyncio.cluster.RedisCluster
RedisClusterClientTypes = redis.cluster.RedisCluster, redis.asyncio.cluster.RedisCluster
RedisClusterClientT = redis.cluster.RedisCluster | redis.asyncio.cluster.RedisCluster
RedisClientTypes = (
    redis.client.Redis,
    redis.cluster.RedisCluster,
    redis.asyncio.client.Redis,
    redis.asyncio.cluster.RedisCluster,
)
RedisClientT = (
    redis.client.Redis | redis.asyncio.client.Redis | redis.cluster.RedisCluster | redis.asyncio.cluster.RedisCluster
)
RedisClientTV = TypeVar("RedisClientTV", bound=RedisClientT)
RedisScriptT = redis.commands.core.Script | redis.commands.core.AsyncScript


SerializerName = Literal["json", "pickle", "dill", "bson", "msgpack", "yaml", "cbor", "cloudpickle"]

HashValueT = bytes | str
"""The sub-key produced by a hasher: the index member and hash-map field name.

Deliberately narrower than ``redis.typing.KeyT``: the library never produces
``memoryview`` sub-keys, and the narrower union keeps composed code compatible
with redis-py APIs typed via constrained type variables.
"""


def is_module(val: Any) -> TypeGuard[ModuleType]:
    return ismodule(val)


def is_redis_async_client(client: RedisClientT) -> TypeGuard[RedisAsyncClientT]:
    """
    Returns True if the given Redis client is an asynchronous client.
    """
    return isinstance(client, RedisAsyncClientTypes)


def is_redis_sync_client(client: RedisClientT) -> TypeGuard[RedisSyncClientT]:
    """
    Returns True if the given Redis client is a synchronous client.
    """
    return isinstance(client, RedisSyncClientTypes)


def is_redis_cluster_client(client: RedisClientT) -> TypeGuard[RedisClusterClientT]:
    """
    Returns True if the given Redis client is a cluster client.
    """
    return isinstance(client, RedisClusterClientTypes)


def is_redis_sync_script(script: RedisScriptT) -> TypeGuard[redis.commands.core.Script]:
    """
    Returns True if the given Redis script is a synchronous script.
    """
    return isinstance(script, redis.commands.core.Script)


def is_redis_async_script(script: RedisScriptT) -> TypeGuard[redis.commands.core.AsyncScript]:
    """
    Returns True if the given Redis script is an asynchronous script.
    """
    return isinstance(script, redis.commands.core.AsyncScript)
