from __future__ import annotations

import json
import weakref
from functools import wraps
from inspect import iscoroutine, iscoroutinefunction
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)

import redis.asyncio.client
import redis.asyncio.cluster
import redis.client
import redis.cluster
import redis.commands.core

from .constants import DEFAULT_MAXSIZE, DEFAULT_PREFIX, DEFAULT_TTL
from .policies.abstract import AbstractPolicy

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, EncodedT, KeyT

    FT = TypeVar("FT", bound=Callable)
    SerializerT = Callable[[Any], EncodedT]
    DeserializerT = Callable[[EncodedT], Any]

__all__ = ("RedisFuncCache",)

RedisClientTV = TypeVar(
    "RedisClientTV",
    bound=Union[
        redis.client.Redis, redis.asyncio.client.Redis, redis.cluster.RedisCluster, redis.asyncio.cluster.RedisCluster
    ],
)


class RedisFuncCache(Generic[RedisClientTV]):
    """A function cache class backed by Redis.

    Attributes:
        __call__: Equivalent to the :meth:`decorate` method.
                  This allows an instance to be used as a :term:`decorator` without parentheses.
    """

    def __init__(
        self,
        name: str,
        policy: Type[AbstractPolicy],
        client: Union[RedisClientTV, Callable[[], RedisClientTV]],
        maxsize: Optional[int] = None,
        ttl: Optional[int] = None,
        prefix: Optional[str] = None,
        serializer: Union[Tuple[SerializerT, DeserializerT], None] = None,
    ):
        """Initializes the Cache instance with the given parameters.

        Args:
            name: The name of the cache manager.

                It is assigned to property :attr:`name`.

            policy: The **class (NOT instance)** for the caching policy

            client: Redis client to use.

                You can pass either an object of one of the following types:

                - :class:`redis.Redis`
                - :class:`redis.asyncio.client.Redis`
                - :class:`redis.cluster.RedisCluster`
                - :class:`redis.asyncio.cluster.RedisCluster`

                or a function that returns one of these objects.

                Access the client via the :attr:`client` property.

                Note:
                    If a function is provided, it will be executed **every time** the :attr:`.client` property is accessed.

            maxsize: The maximum size of the cache.

                If not provided, the default is :data:`.DEFAULT_MAXSIZE`.
                Zero or negative values means no limit.
                Assigned to property :attr:`maxsize`.

            ttl: The time-to-live (in seconds) for cache items.

                If not provided, the default is :data:`.DEFAULT_TTL`.
                Zero or negative values means no set ttl.
                Assigned to property :attr:`ttl`.


            prefix: The prefix for cache keys.

                If not provided, the default is :data:`.DEFAULT_PREFIX`.
                Assigned to property :attr:`prefix`.

            serializer: Optional serialize/deserialize function pair for return value of what decorated.

                If not provided, the cache will use :func:`json.dumps` and :func:`json.loads`.

                ``serializer`` is a pair of callbacks, the first one is used to serialize return value, the second one is used to deserialize return value.

                Here is an example of first(serialize) callback::

                    def my_serializer(value):
                        return msgpack.packb(value, use_bin_type=True)

                And example of second(deserialize) callback::

                    def my_deserializer(data):
                        return msgpack.unpackb(data, raw=False)

                We can then pass the two callbacks to ``serializer`` parameter::

                    my_cache = RedisFuncCache(__name__, MyPolicy, redis_client, serializer=(my_serializer, my_deserializer))

        """
        self._name = name
        self._policy_type = policy
        self._policy_instance: Optional[AbstractPolicy] = None
        self._prefix = prefix or DEFAULT_PREFIX
        self._redis_instance: Optional[RedisClientTV] = None
        self._redis_factory: Optional[Callable[[], RedisClientTV]] = None

        if callable(client):
            self._redis_factory = client
        else:
            self._redis_instance = client
        self._maxsize = DEFAULT_MAXSIZE if maxsize is None else int(maxsize)
        self._ttl = DEFAULT_TTL if ttl is None else int(ttl)
        self._user_return_value_serializer: Optional[SerializerT] = serializer[0] if serializer else None
        self._user_return_value_deserializer: Optional[DeserializerT] = serializer[1] if serializer else None

    @property
    def name(self) -> str:
        """The name of the cache manager."""
        return self._name

    @property
    def prefix(self) -> str:
        """The prefix for cache keys."""
        return self._prefix

    @property
    def policy(self) -> AbstractPolicy:
        """Instance of the caching policy.

        Note:
            This method returns an instance of the policy, not the type or class itself.
            The `policy` argument passed to the constructor, however, is expected to be a type or class.
        """
        if self._policy_instance is None:
            self._policy_instance = self._policy_type(weakref.proxy(self))
        return self._policy_instance

    @property
    def client(self) -> RedisClientTV:
        """The redis client instance used in the cache.

        Attention:
            If what passed to the `client` argument of the constructor is a function,
            it will be executed **every time** the property is accessed.
        """
        if self._redis_instance:
            return self._redis_instance
        if self._redis_factory:
            return self._redis_factory()
        raise RuntimeError("No redis client or factory provided.")

    @property
    def maxsize(self) -> int:
        """The cache's maximum size."""
        return self._maxsize

    @property
    def ttl(self) -> int:
        """time-to-live (in seconds) for the cache"""
        return self._ttl

    def serialize_return_value(self, value: Any) -> EncodedT:
        """Serialize return value of what decorated."""
        if self._user_return_value_serializer:
            return self._user_return_value_serializer(value)
        return json.dumps(value, ensure_ascii=False).encode()

    def deserialize_return_value(self, data: EncodedT) -> Any:
        """Deserialize return value of what decorated."""
        if self._user_return_value_deserializer:
            return self._user_return_value_deserializer(data)
        return json.loads(data)

    @classmethod
    def get(
        cls,
        script: redis.commands.core.Script,
        key_pair: Tuple[KeyT, KeyT],
        hash_: KeyT,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ) -> Optional[EncodedT]:
        """Execute the given Redis Lua script with the provided arguments.

        Args:
            script: Redis Lua script to be evaluated, which should attempt to retrieve the return value from the cache using the given keys and hash.
            key_pair: The key name pair of the Redis set and hash-map data structure used by the cache.
            hash_: The member of the Redis key and also the field name of the Redis hash map.
            ttl: Time-to-live of the cache in seconds.
            options: Reserved for future use.
            ext_args: Extra arguments passed to the Lua script.

        Returns:
            The hit return value, or :data:`None` if the value is missing.
        """
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        return script(keys=key_pair, args=chain((ttl, hash_, encoded_options), ext_args))

    @classmethod
    async def aget(
        cls,
        script: redis.commands.core.AsyncScript,
        key_pair: Tuple[KeyT, KeyT],
        hash_: KeyT,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ) -> Optional[EncodedT]:
        """Async version of :meth:`get`"""
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        return await script(keys=key_pair, args=chain((ttl, hash_, encoded_options), ext_args))

    @classmethod
    def put(
        cls,
        script: redis.commands.core.Script,
        key_pair: Tuple[KeyT, KeyT],
        hash_: KeyT,
        value: EncodableT,
        maxsize: int,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ):
        """Execute the given Redis Lua script with the provided arguments.

        Args:
            script: Redis Lua script to be evaluated, which shall store the return value in the cache.
            key_pair: The key name pair of the Redis set and hash-map data structure used by the cache.
            hash_: The member of the Redis key and also the field name of the Redis hash map.
            ttl: Time-to-live of the cache in seconds.
            options: Reserved for future use.
            ext_args: Extra arguments passed to the Lua script.

        If the cache reaches its :attr:`maxsize`, it will remove one item according to its :attr:`policy` before inserting the new item.
        """
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        script(keys=key_pair, args=chain((maxsize, ttl, hash_, value, encoded_options), ext_args))

    @classmethod
    async def aput(
        cls,
        script: redis.commands.core.AsyncScript,
        key_pair: Tuple[KeyT, KeyT],
        hash_: KeyT,
        value: EncodableT,
        maxsize: int,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ):
        """Async version of :meth:`get`"""
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        await script(keys=key_pair, args=chain((maxsize, ttl, hash_, value, encoded_options), ext_args))

    def exec(self, user_function: Callable, user_args: Sequence, user_kwds: Mapping[str, Any], **options):
        """Execute the given user function with given arguments.

        Args:
            user_function: user function to execute
            user_args: positional arguments to pass to the user function
            user_kwds: keyword arguments to pass to the user function
            options: reserved

        Returns:
            The cached return value if it is cached, otherwise the return value of the user function directly.

        In this method, :meth:`get` is called before the ``user_function``, and :meth:`put` is called afterward.
        """
        script_0, script_1 = self.policy.lua_scripts
        if not (isinstance(script_0, redis.commands.core.Script) and isinstance(script_1, redis.commands.core.Script)):
            raise RuntimeError(
                f"A tuple of two {redis.commands.core.Script} objects is required for execution, but actually got ({script_0!r}, {script_1!r})."
            )
        keys = self.policy.calc_keys(user_function, user_args, user_kwds)
        hash_value = self.policy.calc_hash(user_function, user_args, user_kwds)
        ext_args = self.policy.calc_ext_args(user_function, user_args, user_kwds) or ()
        cached = self.get(script_0, keys, hash_value, self.ttl, options, ext_args)
        if cached is not None:
            return self.deserialize_return_value(cached)
        user_return_value = user_function(*user_args, **user_kwds)
        user_retval_serialized = self.serialize_return_value(user_return_value)
        self.put(script_1, keys, hash_value, user_retval_serialized, self.maxsize, self.ttl, options, ext_args)
        return user_return_value

    async def aexec(self, user_function: Callable, user_args: Sequence, user_kwds: Mapping[str, Any], **options):
        """Async version of :meth:`.exec`"""
        script_0, script_1 = self.policy.lua_scripts
        if not (
            isinstance(script_0, redis.commands.core.AsyncScript)
            and isinstance(script_1, redis.commands.core.AsyncScript)
        ):
            raise RuntimeError(
                f"A tuple of two {redis.commands.core.AsyncScript} objects is required for async execution, but actually got ({script_0!r}, {script_1!r})."
            )
        keys = self.policy.calc_keys(user_function, user_args, user_kwds)
        hash_value = self.policy.calc_hash(user_function, user_args, user_kwds)
        ext_args = self.policy.calc_ext_args(user_function, user_args, user_kwds) or ()
        cached = await self.aget(script_0, keys, hash_value, self.ttl, options, ext_args)
        if cached is not None:
            return self.deserialize_return_value(cached)
        ret_val = user_function(*user_args, **user_kwds)
        if iscoroutine(ret_val):
            user_return_value = await ret_val
        else:
            user_return_value = ret_val
        user_retval_serialized = self.serialize_return_value(user_return_value)
        await self.aput(script_1, keys, hash_value, user_retval_serialized, self.maxsize, self.ttl, options, ext_args)
        return user_return_value

    def decorate(self, user_function: Optional[FT] = None, /, **kwargs) -> FT:
        """Decorate the given function with cache.

        Equivalent to :attr:`__call__`
        """

        def decorator(f: FT):
            @wraps(f)
            def wrapper(*f_args, **f_kwargs):
                return self.exec(f, f_args, f_kwargs, **kwargs)

            @wraps(f)
            async def awrapper(*f_args, **f_kwargs):
                return await self.aexec(f, f_args, f_kwargs, **kwargs)

            return awrapper if iscoroutinefunction(f) else wrapper

        if user_function is None:
            return decorator  # type: ignore
        return decorator(user_function)  # type: ignore

    __call__ = decorate
