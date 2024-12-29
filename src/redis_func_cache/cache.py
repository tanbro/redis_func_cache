from __future__ import annotations

import json
import pickle
import weakref
from functools import wraps
from inspect import isasyncgenfunction, iscoroutine, iscoroutinefunction
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Iterable,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

import redis.asyncio.client
import redis.asyncio.cluster
import redis.client
import redis.cluster
import redis.commands.core

try:  # pragma: no cover
    import msgpack  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    msgpack = None  # type: ignore[assignment]
try:  # pragma: no cover
    import cloudpickle  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    cloudpickle = None  # type: ignore[assignment]

from .constants import DEFAULT_MAXSIZE, DEFAULT_PREFIX, DEFAULT_TTL
from .policies.abstract import AbstractPolicy

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, EncodedT, KeyT

    SerializerT = Callable[[Any], EncodedT]
    DeserializerT = Callable[[EncodedT], Any]
    SerializerPairT = Tuple[SerializerT, DeserializerT]
    SerializerSetterValueT = Union[Literal["json", "pickle", "msgpack", "cloudpickle"], SerializerPairT]

__all__ = ("RedisFuncCache",)

FunctionTV = TypeVar("FunctionTV", bound=Callable)

RedisClientTV = TypeVar(
    "RedisClientTV",
    bound=Union[
        redis.client.Redis, redis.asyncio.client.Redis, redis.cluster.RedisCluster, redis.asyncio.cluster.RedisCluster
    ],
)


class RedisFuncCache(Generic[RedisClientTV]):
    """A function cache class backed by Redis."""

    def __init__(
        self,
        name: str,
        policy: Type[AbstractPolicy],
        client: Union[RedisClientTV, Callable[[], RedisClientTV]],
        maxsize: int = DEFAULT_MAXSIZE,
        ttl: int = DEFAULT_TTL,
        prefix: str = DEFAULT_PREFIX,
        serializer: SerializerSetterValueT = "json",
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

            serializer: Optional serialize/deserialize name or function pair for return value of what decorated.

                If not provided, the cache will use :func:`json.dumps` and :func:`json.loads`.

                - It could be a string, and must be one of the following:

                  - ``"json"``: Use :func:`json.dumps` and :func:`json.loads`
                  - ``"pickle"``: Use :func:`pickle.dumps` and :func:`pickle.loads`
                  - ``"msgpack"``: Use :func:`msgpack.packb` and :func:`msgpack.unpackb`. Only available when :mod:`msgpack` is installed.
                  - ``"cloudpickle"``: Use :func:`cloudpickle.dumps` and :func:`pickle.loads`. Only available when :mod:`cloudpickle` is installed.

                - Or it could be **a PAIR of callbacks**, the first one is used to serialize return value, the second one is used to deserialize return value.

                  Here is an example of first(serialize) callback::

                      def my_serializer(value):
                          return msgpack.packb(value, use_bin_type=True)

                  And and example of second(deserialize) callback::

                      def my_deserializer(data):
                          return msgpack.unpackb(data, raw=False)

                  We can then pass the two callbacks to ``serializer`` parameter::

                      my_cache = RedisFuncCache(
                        __name__,
                        MyPolicy,
                        redis_client,
                        serializer=(my_serializer, my_deserializer)
                    )

        Attributes:
            __call__: Equivalent to the :meth:`decorate` method.
            __serializers__: A dictionary of serializers.
        """
        self.name = name
        self.prefix = prefix
        self.maxsize = maxsize
        self.ttl = ttl
        self._policy_type = policy
        self._policy_instance: Optional[AbstractPolicy] = None
        self._redis_instance: Optional[RedisClientTV] = None
        self._redis_factory: Optional[Callable[[], RedisClientTV]] = None
        if callable(client):
            self._redis_factory = client
        else:
            self._redis_instance = client
        self.serializer = serializer  # type: ignore[assignment]

    __tmp_dict = {}
    __tmp_dict["json"] = (lambda x: json.dumps(x, ensure_ascii=False).encode(), lambda x: json.loads(x))
    __tmp_dict["pickle"] = (lambda x: pickle.dumps(x), lambda x: pickle.loads(x))
    if msgpack:
        __tmp_dict["msgpack"] = (lambda x: msgpack.packb(x), lambda x: msgpack.unpackb(x))  # pyright: ignore[reportOptionalMemberAccess]
    if cloudpickle:
        __tmp_dict["cloudpickle"] = (lambda x: cloudpickle.dumps(x), lambda x: pickle.loads(x))  # pyright: ignore[reportOptionalMemberAccess]
    __serializers__: Mapping[str, SerializerPairT] = __tmp_dict
    del __tmp_dict

    @property
    def name(self) -> str:
        """The name of the cache manager."""
        return self._name

    @name.setter
    def name(self, value: str):
        value = str(value).strip()
        if not value:
            raise ValueError("name must be a non-empty string")
        self._name = value

    @property
    def prefix(self) -> str:
        """The prefix for cache keys."""
        return self._prefix

    @prefix.setter
    def prefix(self, value: str):
        value = str(value).strip()
        if not value:
            raise ValueError("prefix must be a non-empty string")
        self._prefix = value

    @property
    def maxsize(self) -> int:
        """The cache's maximum size."""
        return self._maxsize

    @maxsize.setter
    def maxsize(self, value: int):
        self._maxsize = int(value)

    @property
    def ttl(self) -> int:
        """The time-to-live (in seconds) for cache items."""
        return self._ttl

    @ttl.setter
    def ttl(self, value: int):
        self._ttl = int(value)

    @property
    def serializer(self) -> SerializerPairT:
        """The serializer and deserializer used in the cache.

        The cache use them to serialize/deserialize the return value of what decorated.
        """
        return (self._serializer, self._deserializer)

    @serializer.setter
    def serializer(self, value: SerializerSetterValueT):
        if isinstance(value, str):
            self._serializer, self._deserializer = self.__serializers__[value]
        elif (
            isinstance(value, Sequence)
            and not isinstance(value, (bytes, bytearray, str))
            and len(value) == 2
            and all(callable(x) for x in value)
        ):
            self._serializer, self._deserializer = value
        else:
            raise ValueError("serializer must be a string or a sequence type of a pair of callable objects")

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
    def is_async_client(self) -> bool:
        """Whether the redis client is asynchronous."""
        return isinstance(self.client, (redis.asyncio.client.Redis, redis.asyncio.cluster.RedisCluster))

    def serialize(self, value: Any, f: Optional[SerializerT] = None) -> EncodedT:
        """Serialize return value of what decorated."""
        if f:
            return f(value)
        return self._serializer(value)

    def deserialize(self, data: EncodedT, f: Optional[DeserializerT] = None) -> Any:
        """Deserialize return value of what decorated."""
        if f:
            return f(data)
        return self._deserializer(data)

    @classmethod
    def get(
        cls,
        script: redis.commands.core.Script,
        key_pair: Tuple[KeyT, KeyT],
        hash_value: KeyT,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ) -> Optional[EncodedT]:
        """Execute the given Redis Lua script with the provided arguments.

        Args:
            script: Redis Lua script to be evaluated, which should attempt to retrieve the return value from the cache using the given keys and hash.
            key_pair: The key name pair of the Redis set and hash-map data structure used by the cache.
            hash_value: The member of the Redis key and also the field name of the Redis hash map.
            ttl: Time-to-live of the cache in seconds.
            options: Reserved for future use.
            ext_args: Extra arguments passed to the Lua script.

        Returns:
            The hit return value, or :data:`None` if the value is missing.
        """
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        return script(keys=key_pair, args=chain((ttl, hash_value, encoded_options), ext_args))

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
        hash_value: KeyT,
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
            hash_value: The member of the Redis key and also the field name of the Redis hash map.
            ttl: Time-to-live of the cache in seconds.
            options: Reserved for future use.
            ext_args: Extra arguments passed to the Lua script.

        If the cache reaches its :attr:`maxsize`, it will remove one item according to its :attr:`policy` before inserting the new item.
        """
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        script(keys=key_pair, args=chain((maxsize, ttl, hash_value, value, encoded_options), ext_args))

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

    def _before_get(self, user_function, user_args, user_kwds):
        keys = self.policy.calc_keys(user_function, user_args, user_kwds)
        hash_value = self.policy.calc_hash(user_function, user_args, user_kwds)
        ext_args = self.policy.calc_ext_args(user_function, user_args, user_kwds) or ()
        return keys, hash_value, ext_args

    def exec(
        self,
        user_function: Callable,
        user_args: Sequence,
        user_kwds: Mapping[str, Any],
        serializer: Optional[SerializerT] = None,
        deserializer: Optional[DeserializerT] = None,
        **options,
    ):
        """Execute the given user function with the provided arguments.

        Args:
            user_function: The user function to execute.
            user_args: Positional arguments to pass to the user function.
            user_kwds: Keyword arguments to pass to the user function.
            serializer: Custom serializer passed from :meth:`decorate`.
            deserializer: Custom deserializer passed from :meth:`decorate`.
            options: Additional options passed from :meth:`decorate`'s `**kwargs`.

        Returns:
            The cached return value if it exists in the cache; otherwise, the direct return value of the user function.

        Notes:
            This method first calls :meth:`get` to attempt retrieving a cached result before executing the ``user_function``.
            If no cached result is found, it executes the ``user_function``, then calls :meth:`put` to store the result in the cache.
        """
        script_0, script_1 = self.policy.lua_scripts
        if not (isinstance(script_0, redis.commands.core.Script) and isinstance(script_1, redis.commands.core.Script)):
            raise RuntimeError(
                f"A tuple of two {redis.commands.core.Script} objects is required for execution, but actually got ({script_0!r}, {script_1!r})."
            )
        keys, hash_value, ext_args = self._before_get(user_function, user_args, user_kwds)
        cached_return_value = self.get(script_0, keys, hash_value, self.ttl, options, ext_args)
        if cached_return_value is not None:
            return self.deserialize(cached_return_value, deserializer)
        user_return_value = user_function(*user_args, **user_kwds)
        user_retval_serialized = self.serialize(user_return_value, serializer)
        self.put(script_1, keys, hash_value, user_retval_serialized, self.maxsize, self.ttl, options, ext_args)
        return user_return_value

    async def aexec(
        self,
        user_function: Callable,
        user_args: Sequence,
        user_kwds: Mapping[str, Any],
        serializer: Optional[SerializerT] = None,
        deserializer: Optional[DeserializerT] = None,
        **options,
    ):
        """Async version of :meth:`.exec`"""
        script_0, script_1 = self.policy.lua_scripts
        if not (
            isinstance(script_0, redis.commands.core.AsyncScript)
            and isinstance(script_1, redis.commands.core.AsyncScript)
        ):
            raise RuntimeError(
                f"A tuple of two {redis.commands.core.AsyncScript} objects is required for async execution, but actually got ({script_0!r}, {script_1!r})."
            )
        keys, hash_value, ext_args = self._before_get(user_function, user_args, user_kwds)
        cached = await self.aget(script_0, keys, hash_value, self.ttl, options, ext_args)
        if cached is not None:
            return self.deserialize(cached, deserializer)
        ret_val = user_function(*user_args, **user_kwds)
        if iscoroutine(ret_val):
            user_return_value = await ret_val
        else:
            user_return_value = ret_val
        user_retval_serialized = self.serialize(user_return_value, serializer)
        await self.aput(script_1, keys, hash_value, user_retval_serialized, self.maxsize, self.ttl, options, ext_args)
        return user_return_value

    def decorate(
        self,
        user_function: Optional[FunctionTV] = None,
        /,
        serializer: Optional[SerializerT] = None,
        deserializer: Optional[DeserializerT] = None,
        **keywords,
    ) -> FunctionTV:
        """Decorate the given function with caching.

        Args:
            user_function: The function to be decorated.
            serializer: Custom serialize function for the return value of the user function. If defined, it overrides the first element of :attr:`serializer`.
            deserializer: Custom deserialize function for the return value of the user function. If defined, it overrides the second element of :attr:`serializer`.
            **keywords: Additional options passed to :meth:`exec`, they will encoded to json, then pass to redis lua script.

        This method is equivalent to :attr:`__call__`.

        Example:
            Once we create a cache instance::

                from redis_func_cache import RedisFuncCache

                cache = RedisFuncCache("my_cache", MyPolicy, redis_client)

            We can use it as a decorator, either the instance itself or the :meth:`decorate` method, with or without parentheses::

                @cache
                def my_func(a, b):
                    return a + b

            or::

                @cache()
                def my_func(a, b):
                    return a + b

            or::

                @cache.decorate
                def my_func(a, b):
                    return a + b

            or::

                @cache.decorate()
                def my_func(a, b):
                    return a + b


            or::

                @cache(serializer=my_serializer, deserializer=my_deserializer)
                def my_func(a, b):
                    return a + b

            or::

                @cache.decorate(serializer=my_serializer, deserializer=my_deserializer)
                def my_func(a, b):
                    return a + b

        Note:
            The `serializer` and `deserializer` only affect the currently decorated function.
        """

        def decorator(f: FunctionTV):
            @wraps(f)
            def wrapper(*f_args, **f_kwargs):
                return self.exec(f, f_args, f_kwargs, serializer, deserializer, **keywords)

            @wraps(f)
            async def awrapper(*f_args, **f_kwargs):
                return await self.aexec(f, f_args, f_kwargs, serializer, deserializer, **keywords)

            if iscoroutinefunction(f) or isasyncgenfunction(f):
                return cast(FunctionTV, awrapper)
            return cast(FunctionTV, wrapper)

        if user_function is None:
            return cast(FunctionTV, decorator)
        return cast(FunctionTV, decorator(user_function))

    __call__ = decorate
