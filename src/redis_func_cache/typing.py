from __future__ import annotations

import sys
from collections.abc import Callable
from inspect import ismodule
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypeGuard, TypeVar

if TYPE_CHECKING:  # pragma: no cover
    if sys.version_info < (3, 11):  # pragma: no cover
        from typing_extensions import Self
    else:  # pragma: no cover
        from typing import Self

    from _typeshed import ReadableBuffer

import redis.asyncio.client
import redis.asyncio.cluster
import redis.client
import redis.cluster
import redis.commands.core
from redis.typing import EncodedT, KeyT

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


class HashProtocol(Protocol):
    def update(self, data: ReadableBuffer, /) -> None: ...
    def digest(self) -> bytes: ...
    def hexdigest(self) -> str: ...
    def copy(self) -> Self: ...


class HandlerProtocol(Protocol):
    def before_deserialize(
        self,
        value: EncodedT,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...
    def after_deserialize(
        self,
        value: Any,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...
    def before_serialize(
        self,
        value: Any,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...
    def after_serialize(
        self,
        value: EncodedT,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> Any: ...

    async def before_deserialize_async(
        self,
        value: EncodedT,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...
    async def after_deserialize_async(
        self,
        value: Any,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...
    async def before_serialize_async(
        self,
        value: Any,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> tuple[bool, Any]: ...
    async def after_serialize_async(
        self,
        value: EncodedT,
        *,
        keys: tuple[KeyT, KeyT],
        hash_value: KeyT,
        func: Callable | None = None,
        args: tuple | None = None,
        kwds: dict | None = None,
    ) -> Any: ...


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
