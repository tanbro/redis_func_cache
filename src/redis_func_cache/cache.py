from __future__ import annotations

import json
import pickle
import weakref
from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar, Token
from copy import copy
from dataclasses import dataclass, replace
from functools import wraps
from inspect import BoundArguments, iscoroutinefunction, signature
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Generic,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)
from warnings import warn

import redis.commands.core

try:  # pragma: no cover
    import bson  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    bson = None  # type: ignore[assignment]
try:  # pragma: no cover
    import cloudpickle  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    cloudpickle = None  # type: ignore[assignment]
try:  # pragma: no cover
    import msgpack  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    msgpack = None  # type: ignore[assignment]
try:
    import cbor2  # type: ignore[import-not-found]
except ImportError:
    cbor2 = None  # type: ignore[assignment]
try:  # pragma: no cover
    import yaml  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]
else:
    if yaml.__with_libyaml__:
        from yaml import CSafeDumper as YamlDumper  # type: ignore[import-not-found]
        from yaml import CSafeLoader as YamlLoader  # type: ignore[import-not-found]
    else:
        from yaml import SafeDumper as YamlDumper  # type: ignore[assignment, import-not-found]
        from yaml import SafeLoader as YamlLoader  # type: ignore[assignment, import-not-found]


from .constants import DEFAULT_MAXSIZE, DEFAULT_PREFIX, DEFAULT_TTL
from .exceptions import CacheMissError
from .policies.abstract import AbstractPolicy
from .typing import CallableTV, RedisClientTV, SerializerName

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, EncodedT, KeyT

    SerializerT = Callable[[Any], EncodedT]
    DeserializerT = Callable[[EncodedT], Any]
    SerializerPairT = Tuple[SerializerT, DeserializerT]
    SerializerSetterValueT = Union[SerializerName, SerializerPairT]

__all__ = ("RedisFuncCache",)


class RedisFuncCache(Generic[RedisClientTV]):
    """A function cache class backed by Redis.

    This class provides a decorator-based caching mechanism for functions, storing their results in Redis.
    It supports both synchronous and asynchronous Redis clients, customizable cache policies, and flexible serialization options.

    ::

        >>> from redis_func_cache import LruTPolicy, RedisFuncCache
        >>> cache = RedisFuncCache("my_cache", LruTPolicy, redis_client)
        >>> @cache
        ... def my_func(a, b):
        ...     return a + b

    - The `serializer` parameter can be a string or a pair of callables.
    - If a callable is passed as the `redis_client`, it will be invoked every time the redis client is accessed.
    - The cache supports both synchronous and asynchronous Redis clients, but the decorated function must match the redis client's async/sync nature.
    """

    @dataclass
    class Mode:
        """A :func:`dataclasses.dataclass` for cache operation mode flags.

        Defines how the cache behaves when executing decorated functions.

        .. versionadded:: 0.5
        """

        read: bool = True
        """Allow reading from cache backend"""
        write: bool = True
        """Allow writing to cache backend"""
        exec: bool = True
        """Allow function execution"""

    @dataclass
    class Stats:
        """A :func:`dataclasses.dataclass` for cache operation statistics.

        .. versionadded:: 0.5
        """

        count: int = 0
        """Number of cache operations"""
        read: int = 0
        """Number of read operations"""
        write: int = 0
        """Number of write operations"""
        exec: int = 0
        """Number of function execution operations"""
        miss: int = 0
        """Number of cache misses"""
        hit: int = 0
        """Number of cache hits"""

    def __init__(
        self,
        name: str,
        policy: Type[AbstractPolicy],
        client: Union[RedisClientTV, Callable[[], RedisClientTV]],
        maxsize: int = DEFAULT_MAXSIZE,
        ttl: int = DEFAULT_TTL,
        update_ttl: bool = True,
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

                Get the client via :meth:`get_client`.

                Caution:
                    When using the factory pattern
                    (a :term:`callable` object is passed to the ``client`` :term:`argument` of the constructor),
                    the factory function will be invoked **every time** when :meth:`get_client` is called, or the cache instance requires a redis client internally.

            maxsize: The maximum size of the cache.

                - If ``None`` or not provided, the default is :data:`.DEFAULT_MAXSIZE`.
                - Zero or negative values will cause a :class:`ValueError`.

                Assigned to property :attr:`maxsize`.

            ttl: The time-to-live (in seconds) for the whole cache data structures on Redis backend.

                - If ``None`` or not provided, the default is :data:`.DEFAULT_TTL`.
                - Zero or negative values will cause a :class:`ValueError`.

                Assigned to property :attr:`ttl`.

            update_ttl: Whether to update the TTL of the whole cache data structures on Redis backend when they are accessed.

                - When ``True`` (default), accessing a cached item will reset its TTL.
                - When ``False``, accessing a cached item will not update its TTL.

                Assigned to property :attr:`update_ttl`.

                .. versionadded:: 0.5

            prefix: The prefix for cache keys.

                If not provided, the default is :data:`.DEFAULT_PREFIX`.

                Assigned to property :attr:`prefix`.

            serializer: Optional serialize/deserialize name or function pair for return value of what decorated.

                If not provided, the cache will use :func:`json.dumps` and :func:`json.loads`.

                - It could be a string, and must be one of the following:

                  - ``"json"``: Use :func:`json.dumps` and :func:`json.loads`
                  - ``"pickle"``: Use :func:`pickle.dumps` and :func:`pickle.loads`
                  - ``"bson"``: Use :func:`bson.decode` and :func:`bson.encode`. Only available when ``pymongo`` is installed.
                  - ``"msgpack"``: Use :func:`msgpack.packb` and :func:`msgpack.unpackb`. Only available when :mod:`msgpack` is installed.
                  - ``"cbor"``: Use :func:`cbor.dumps` and :func:`cbor.loads`. Only available when :mod:`cbor2` is installed.
                  - ``"yaml"``: Use ``yaml.dump`` and ``yaml.load``. Only available when ``yaml`` is installed.
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
                          __name__, MyPolicy, redis_client, serializer=(my_serializer, my_deserializer)
                      )

        Attributes:
            __call__: Equivalent to the :meth:`decorate` method.
            __serializers__ (Dict[str, SerializerPairT]): A dictionary of serializers.
        """
        self.name = name
        self.prefix = prefix
        self.maxsize = maxsize
        self.ttl = ttl
        self.update_ttl = update_ttl
        self._policy_type = policy
        self._policy_instance: Optional[AbstractPolicy] = None
        self._redis_instance: Optional[RedisClientTV] = None
        self._redis_factory: Optional[Callable[[], RedisClientTV]] = None
        if callable(client):
            self._redis_factory = client
        else:
            self._redis_instance = client
        self.serializer = serializer  # type: ignore[assignment]
        self._mode: ContextVar[RedisFuncCache.Mode] = ContextVar("mode", default=RedisFuncCache.Mode())
        self._stats: ContextVar[Optional[RedisFuncCache.Stats]] = ContextVar("stats", default=None)

    __serializers__: Dict[str, SerializerPairT] = {
        "json": (lambda x: json.dumps(x).encode(), lambda x: json.loads(x)),
        "pickle": (lambda x: pickle.dumps(x), lambda x: pickle.loads(x)),
    }
    if bson is not None:
        __serializers__["bson"] = (
            lambda x: bson.encode({"": x}),  # pyright: ignore[reportOptionalMemberAccess]
            lambda x: bson.decode(x)[""],  # pyright: ignore[reportOptionalMemberAccess]
        )
    if msgpack is not None:
        __serializers__["msgpack"] = (  # pyright: ignore[reportArgumentType]
            lambda x: msgpack.packb(x),  # pyright: ignore[reportOptionalMemberAccess]
            lambda x: msgpack.unpackb(x),  # pyright: ignore[reportOptionalMemberAccess]
        )
    if cbor2 is not None:
        __serializers__["cbor"] = (
            lambda x: cbor2.dumps(x),  # pyright: ignore[reportOptionalMemberAccess]
            lambda x: cbor2.loads(x),  # pyright: ignore[reportOptionalMemberAccess]
        )
    if yaml is not None:
        __serializers__["yaml"] = (
            lambda x: yaml.dump(x, Dumper=YamlDumper).encode(),  # pyright: ignore[reportOptionalMemberAccess,reportPossiblyUnboundVariable]
            lambda x: yaml.load(x, Loader=YamlLoader),  # pyright: ignore[reportOptionalMemberAccess,reportPossiblyUnboundVariable]
        )
    if cloudpickle is not None:
        __serializers__["cloudpickle"] = (
            lambda x: cloudpickle.dumps(x),  # pyright: ignore[reportOptionalMemberAccess]
            lambda x: pickle.loads(x),  # pyright: ignore[reportOptionalMemberAccess]
        )

    @property
    def name(self) -> str:
        """The name of the cache instance."""
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
        """The cache's maximum capacity size."""
        return self._maxsize

    @maxsize.setter
    def maxsize(self, value: int):
        if not value > 0:
            raise ValueError("maxsize must be a greater than 0")
        self._maxsize = int(value)

    @property
    def ttl(self) -> int:
        """The time-to-live (in seconds) of the whole cache structure."""
        return self._ttl

    @ttl.setter
    def ttl(self, value: int):
        if not value > 0:
            raise ValueError("ttl must be a greater than 0")
        self._ttl = int(value)

    @property
    def update_ttl(self) -> bool:
        """Whether to update the TTL of whole cache structure each time accessed."""
        return self._update_ttl

    @update_ttl.setter
    def update_ttl(self, value: bool):
        self._update_ttl = bool(value)

    @property
    def serializer(self) -> SerializerPairT:
        """The serializer and deserializer pair used by the cache.

        This property returns a :class:`tuple` of two :term:`callable` objects:

        #. The first :term:`callable` is the serializer, which converts data into a storable format.
        #. The second :term:`callable` is the deserializer, which reconstructs the original data from the stored format.

        These are used to serialize and deserialize the return values of decorated functions.
        """
        return (self._serializer, self._deserializer)

    @serializer.setter
    def serializer(self, value: SerializerSetterValueT):
        if isinstance(value, str):
            try:
                self._serializer, self._deserializer = self.__serializers__[value]
            except KeyError:
                raise ValueError(f"Unknown serializer: {value}")
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
            The property returns an instance of the policy, not a type or class object.
            While the :term:`argument` ``policy`` of constructor, however, is expected to be a type or class object, not an instance.
        """
        if self._policy_instance is None:
            self._policy_instance = self._policy_type(weakref.proxy(self))
        return self._policy_instance

    def get_client(self) -> RedisClientTV:
        """Get the redis client instance used in the cache.

        Returns:
            The redis client instance used in the cache.

        - If a redis client instance was passed to the cache constructor, it will be returned.
        - If a :term:`callable` object that returns a redis client was passed to the cache constructor (factory pattern), it returns what returned by the factory function.

        Caution:
            When using the factory pattern
            (a :term:`callable` object is passed to the ``client`` :term:`argument` of the constructor),
            the factory function will be invoked **every time** when this method is called, or the cache instance requires a redis client internally.

        .. versionadded:: 0.5
        """
        if self._redis_instance:
            return self._redis_instance
        if self._redis_factory:
            return self._redis_factory()
        raise RuntimeError("No redis client or factory provided.")

    @property
    def client(self) -> RedisClientTV:  # pragma: no cover
        """
        Equivalent to call :meth:`get_client`.

        .. deprecated:: 0.5
            use :meth:`get_client` instead.
        """
        warn("property `client` is deprecated, use `get_client()` instead", DeprecationWarning)
        return self.get_client()

    def serialize(self, value: Any, f: Optional[SerializerT] = None) -> EncodedT:
        """Serialize the return value of the decorated function.

        Args:
            value: The value to be serialized.
            f: A custom serializer function. Defaults to :data:`None`, which means the class's default serializer will be used.

        Returns:
            The serialized value.
        """
        if f:
            return f(value)
        return self._serializer(value)

    def deserialize(self, data: EncodedT, f: Optional[DeserializerT] = None) -> Any:
        """Deserialize the return value of the decorated function.

        Args:
            data: The serialized data to be deserialized.
            f: A custom deserializer function. Defaults to :data:`None`, which means the class's default deserializer will be used.

        Returns:
            The deserialized value.
        """
        if f:
            return f(data)
        return self._deserializer(data)

    @classmethod
    def get(
        cls,
        script: redis.commands.core.Script,
        keys: Tuple[KeyT, KeyT],
        hash_value: KeyT,
        update_ttl: bool,
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
        return script(keys=keys, args=chain((int(update_ttl), ttl, hash_value, encoded_options), ext_args))

    @classmethod
    async def aget(
        cls,
        script: redis.commands.core.AsyncScript,
        keys: Tuple[KeyT, KeyT],
        hash_: KeyT,
        update_ttl: bool,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ) -> Optional[EncodedT]:
        """Async version of :meth:`get`"""
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        return await script(keys=keys, args=chain((int(update_ttl), ttl, hash_, encoded_options), ext_args))

    @classmethod
    def put(
        cls,
        script: redis.commands.core.Script,
        keys: Tuple[KeyT, KeyT],
        hash_value: KeyT,
        value: EncodableT,
        maxsize: int,
        update_ttl: bool,
        ttl: int,
        field_ttl: int = 0,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ):
        """Execute the given Redis Lua script with the provided arguments.

        Args:
            script: Redis Lua script to be evaluated, which shall store the return value in the cache.
            key_pair: The key name pair of the Redis set and hash-map data structure used by the cache.
            hash_value: The member of the Redis key and also the field name of the Redis hash map.
            value: The value to be stored in the hash map.
            ttl: Time-to-live of the cache in seconds.
            field_ttl: Time-to-live of the field name of the Redis hash map.
            options: Reserved for future use.
            ext_args: Extra arguments passed to the Lua script.

        If the cache reaches its :attr:`maxsize`, it will remove one item according to its :attr:`policy` before inserting the new item.
        """
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        script(
            keys=keys,
            args=chain((maxsize, int(update_ttl), ttl, hash_value, value, field_ttl, encoded_options), ext_args),
        )

    @classmethod
    async def aput(
        cls,
        script: redis.commands.core.AsyncScript,
        keys: Tuple[KeyT, KeyT],
        hash_: KeyT,
        value: EncodableT,
        maxsize: int,
        update_ttl: bool,
        ttl: int,
        field_ttl: int = 0,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ):
        """Async version of :meth:`put`"""
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        await script(
            keys=keys, args=chain((maxsize, int(update_ttl), ttl, hash_, value, field_ttl, encoded_options), ext_args)
        )

    @classmethod
    def make_bound(
        cls,
        user_func: Callable,
        user_args: Tuple[Any, ...],
        user_kwds: Dict[str, Any],
        excludes: Sequence[str] | None = None,
        excludes_positional: Sequence[int] | None = None,
    ) -> Optional[BoundArguments]:
        if not excludes and not excludes_positional:
            return None
        sig = signature(user_func)
        bound = sig.bind(*user_args, **user_kwds)
        if excludes_positional:
            bound.arguments = OrderedDict(
                item for i, item in enumerate(bound.arguments.items()) if i not in excludes_positional
            )
        if excludes:
            bound.arguments = OrderedDict((k, v) for k, v in bound.arguments.items() if k not in excludes)
        return bound

    def prepare(
        self,
        user_function: Callable,
        user_args: Tuple[Any, ...],
        user_kwds: Dict[str, Any],
        bound: Optional[BoundArguments] = None,
    ) -> Tuple[Tuple[KeyT, KeyT], KeyT, Iterable[EncodableT]]:
        if bound is None:
            args, kwds = user_args, user_kwds
        else:
            args, kwds = bound.args, bound.kwargs
        keys = self.policy.calc_keys(user_function, args, kwds)
        hash_value = self.policy.calc_hash(user_function, args, kwds)
        ext_args = self.policy.calc_ext_args(user_function, args, kwds) or ()
        return keys, hash_value, ext_args

    def exec(
        self,
        user_function: Callable,
        user_args: Tuple[Any, ...],
        user_kwds: Dict[str, Any],
        serialize_func: Optional[SerializerT] = None,
        deserialize_func: Optional[DeserializerT] = None,
        bound: Optional[BoundArguments] = None,
        field_ttl: int = 0,
        **options,
    ) -> Any:
        """Execute the given user function with the provided arguments.

        Args:
            user_function: The user function to execute.
            user_args: Positional arguments to pass to the user function.
            user_kwds: Keyword arguments to pass to the user function.
            serialize_func: Custom serializer passed from :meth:`decorate`.
            deserialize_func: Custom deserializer passed from :meth:`decorate`.

            bound: Filtered bound arguments which will be used by the policy of the cache.

                - If it is provided, the policy will only use the filtered arguments to calculate the cache key and hash value.
                - If it is not provided, the policy will use all arguments to calculate the cache key and hash value.

            field_ttl: Time-to-live (in seconds) for the cached field.
            options: Additional options from :meth:`decorate`'s `**kwargs`.

        Returns:
            The cached return value if it exists in the cache; otherwise, the direct return value of the user function.

        Notes:
            This method first calls :meth:`get` to attempt retrieving a cached result before executing the ``user_function``.
            If no cached result is found, it executes the ``user_function``, then calls :meth:`put` to store the result in the cache.
        """
        mode = self._mode.get()
        stats = self._stats.get()
        script_0, script_1 = self.policy.lua_scripts
        if not (isinstance(script_0, redis.commands.core.Script) and isinstance(script_1, redis.commands.core.Script)):
            raise TypeError("Can not eval redis lua script in asynchronous mode on a synchronous redis client")
        if stats:
            stats.count += 1
        keys, hash_value, ext_args = self.prepare(user_function, user_args, user_kwds, bound)
        # Only attempt to get from cache if mode has READ flag
        cached = None
        if mode.read:
            cached = self.get(script_0, keys, hash_value, self.update_ttl, self.ttl, options, ext_args)
            if stats:
                stats.read += 1
            if cached is None:
                if stats:
                    stats.miss += 1
            else:
                if stats:
                    stats.hit += 1
                return self.deserialize(cached, deserialize_func)
        # Only attempt to execute if mode has not NO_EXEC flag
        if not mode.exec:
            raise CacheMissError("The cache does not hit and function will not execute")
        user_retval = user_function(*user_args, **user_kwds)
        if stats:
            stats.exec += 1
        # Only put to cache if mode has WRITE flag
        if mode.write:
            user_retval_serialized = self.serialize(user_retval, serialize_func)
            self.put(
                script_1,
                keys,
                hash_value,
                user_retval_serialized,
                self.maxsize,
                self.update_ttl,
                self.ttl,
                0 if field_ttl is None else field_ttl,
                options,
                ext_args,
            )
            if stats:
                stats.write += 1
        return user_retval

    async def aexec(
        self,
        user_function: Callable[..., Coroutine],
        user_args: Tuple[Any, ...],
        user_kwds: Dict[str, Any],
        serialize_func: Optional[SerializerT] = None,
        deserialize_func: Optional[DeserializerT] = None,
        bound: Optional[BoundArguments] = None,
        field_ttl: int = 0,
        **options,
    ) -> Any:
        """Asynchronous version of :meth:`.exec`

        Args:
            user_function: The user function to execute.
            user_args: Positional arguments to pass to the user function.
            user_kwds: Keyword arguments to pass to the user function.
            serialize_func: Custom serializer passed from :meth:`decorate`.
            deserialize_func: Custom deserializer passed from :meth:`decorate`.

            bound: Filtered bound arguments which will be used by the policy of the cache.

                - If it is provided, the policy will only use the filtered arguments to calculate the cache key and hash value.
                - If it is not provided, the policy will use all arguments to calculate the cache key and hash value.

            field_ttl: Time-to-live (in seconds) for the cached field.
            options: Additional options from :meth:`decorate`'s `**kwargs`.
        """
        mode = self._mode.get()
        stats = self._stats.get()
        script_0, script_1 = self.policy.lua_scripts
        if not (
            isinstance(script_0, redis.commands.core.AsyncScript)
            and isinstance(script_1, redis.commands.core.AsyncScript)
        ):
            raise TypeError("Can not eval redis lua script in synchronous mode on an asynchronous redis client")
        if stats:
            stats.count += 1
        keys, hash_value, ext_args = self.prepare(user_function, user_args, user_kwds, bound)
        # Only attempt to get from cache if mode has READ flag
        cached = None
        if mode.read:
            cached = await self.aget(script_0, keys, hash_value, self.update_ttl, self.ttl, options, ext_args)
            if stats:
                stats.read += 1
            if cached is None:
                if stats:
                    stats.miss += 1
            else:
                if stats:
                    stats.hit += 1
                return self.deserialize(cached, deserialize_func)
        # Only attempt to execute if mode has not NO_EXEC flag
        if not mode.exec:
            raise CacheMissError("The cache does not hit and function will not execute")
        user_retval = await user_function(*user_args, **user_kwds)
        if stats:
            stats.exec += 1
        # Only put to cache if mode has WRITE flag
        if mode.write:
            user_retval_serialized = self.serialize(user_retval, serialize_func)
            await self.aput(
                script_1,
                keys,
                hash_value,
                user_retval_serialized,
                self.maxsize,
                self.update_ttl,
                self.ttl,
                0 if field_ttl is None else field_ttl,
                options,
                ext_args,
            )
            if stats:
                stats.write += 1
        return user_retval

    def decorate(
        self,
        user_function: Optional[CallableTV] = None,
        /,
        *,
        serializer: Optional[SerializerSetterValueT] = None,
        ttl: Optional[int] = None,
        excludes: Optional[Sequence[str]] = None,
        excludes_positional: Optional[Sequence[int]] = None,
        **options,
    ) -> CallableTV:
        """Decorate the given function with caching.

        Args:
            user_function: The function to be decorated.

            serializer: serialize/deserialize name or function pair for return value of what decorated.

                It accepts either:
                - A string key mapping to predefined serializers (like "yaml" or "json")
                - A tuple of (`serialize_func`, `deserialize_func`) functions

                If assigned, it overwrite the :attr:`serializer` property of the cache instance on the decorated function.

            ttl: (_Experimental_) The time-to-live (in seconds) for the cached result.

                Note:
                    This parameter specifies the expiration time for a single invocation result, not for the entire cache.

                Caution:
                    The expiration is based on [Redis Hashes Field expiration](https://redis.io/docs/latest/develop/data-types/hashes/#field-expiration).
                    Therefore, expiration only applies to the hash field and does not decrease the total item count in the cache when a field expires.

                Warning:
                    Experimental and only available in Redis versions above 7.4`

            excludes: Optional sequence of parameter names specifying keyword arguments to exclude from cache key generation.

                Example:

                    ::

                        @cache(excludes=["session", "token"])
                        def update_user(user_id: int, session: Session, token: str) -> None: ...

            excludes_positional: Optional sequence of indices specifying positional arguments to exclude from cache key generation.

                Example:

                    ::

                        @cache(excludes_positional=[1, 2])
                        def update_user(user_id: int, session: Session, token: str) -> None: ...

            options: Additional options passed to :meth:`exec`, they will encoded to json, then pass to redis lua script.

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

                @cache(serializer=(lambda x: yaml.safe_dump(x), lambda y: yaml.safe_load(y)))
                def my_func(a, b):
                    return a + b

            or::

                @cache.decorate(serializer="yaml")
                def my_func(a, b):
                    return a + b

        Note:
            The `serializer` parameter only affect the currently decorated function.
        """

        serialize_func: Optional[SerializerT] = None
        deserialize_func: Optional[DeserializerT] = None
        if isinstance(serializer, str):
            serialize_func, deserialize_func = self.__serializers__[serializer]
        elif serializer is not None:
            serialize_func, deserialize_func = serializer
        field_ttl = 0 if ttl is None else int(ttl)

        def decorator(user_func: CallableTV) -> CallableTV:
            @wraps(user_func)
            def wrapper(*user_args, **user_kwargs):
                bound = self.make_bound(user_func, user_args, user_kwargs, excludes, excludes_positional)
                return self.exec(
                    user_func,
                    user_args,
                    user_kwargs,
                    serialize_func,
                    deserialize_func,
                    bound,
                    field_ttl,
                    **options,
                )

            @wraps(user_func)
            async def awrapper(*user_args, **user_kwargs):
                bound = self.make_bound(user_func, user_args, user_kwargs, excludes, excludes_positional)
                return await self.aexec(
                    user_func,
                    user_args,
                    user_kwargs,
                    serialize_func,
                    deserialize_func,
                    bound,
                    field_ttl,
                    **options,
                )

            if not callable(user_func):
                raise TypeError("Can not decorate a non-callable object.")
            if iscoroutinefunction(user_func):
                return cast(CallableTV, awrapper)
            else:
                return cast(CallableTV, wrapper)

        if user_function is None:
            return cast(CallableTV, decorator)
        return cast(CallableTV, decorator(user_function))

    __call__ = decorate

    def get_mode(self) -> RedisFuncCache.Mode:
        """Return a **copy** of the cache mode.

        The cache mode inside the class instance is contextual variable, which is thread local and thread safe.

        .. versionadded:: 0.5
        """
        return copy(self._mode.get())

    def set_mode(self, mode: RedisFuncCache.Mode) -> Token[RedisFuncCache.Mode]:
        """
        .. versionadded:: 0.5
        """
        return self._mode.set(mode)

    def reset_mode(self, token: Token[RedisFuncCache.Mode]):
        """
        .. versionadded:: 0.5
        """
        self._mode.reset(token)

    @contextmanager
    def mode_context(self, mode: RedisFuncCache.Mode) -> Generator[RedisFuncCache.Mode]:
        """A context manager to control cache behavior.

        This context manager allows you to temporarily change cache mode flags.
        It's useful for temporarily disabling specific cache capabilities (e.g., disabling cache writes while keeping reads enabled).

        The context manager is thread local and thread safe.

        Args:
            mode(Mode): The cache mode to use within the context. Can be a combination of Mode bitwise flags.

        Example:

            ::

                @cache
                def func(): ...


                mode = cache.get_mode()
                mode.write = False

                with cache.mode_context(mode):
                    result = func()  # will be executed without cache write

        .. versionadded:: 0.5
        """
        token = self._mode.set(mode)
        try:
            yield mode
        finally:
            self._mode.reset(token)

    @contextmanager
    def disable_rw(self) -> Generator[RedisFuncCache.Mode]:
        """A context manager who disables the cache read and write temporarily.

        This wall disable the cache read and write, as if there is no cache.

        Example:

            ::

                @cache
                def func(): ...


                with cache.disable_rw():
                    result = func()  # will be executed without cache ability

        .. versionadded:: 0.5
        """
        mode = replace(self._mode.get(), read=False, write=False)
        with self.mode_context(mode) as x:
            yield x

    @contextmanager
    def read_only(self) -> Generator[RedisFuncCache.Mode]:
        """A context manager that only reads from cache but does not write to cache.

        It doesn't execute the function if the cache was hit.

        A :class:`CacheMissError` will be raised if the cache was missed in readonly mode.

        Example:

            ::

                @cache
                def func(): ...


                with cache.read_only():
                    result = func()

        .. versionadded:: 0.5
        """
        mode = replace(self._mode.get(), read=True, write=False)
        with self.mode_context(mode) as x:
            yield x

    @contextmanager
    def write_only(self) -> Generator[RedisFuncCache.Mode]:
        """A context manager that bypasses cache retrieval but still writes the result to cache.

        Example:

            ::

                @cache
                def func(): ...


                with cache.disable_read():
                    result = func()  # will be executed and result stored in cache, but not read from cache

        .. versionadded:: 0.5
        """
        mode = replace(self._mode.get(), read=False, write=True)
        with self.mode_context(mode) as x:
            yield x

    @contextmanager
    def stats_context(self, stats: Optional[RedisFuncCache.Stats] = None) -> Generator[RedisFuncCache.Stats]:
        """A context manager that yields a :class:`Stats` object.

        Args:
            stats(Stats): The initial object to make the statistics. If ``None``, a new ``stats`` object will be created.

        .. versionadded:: 0.5
        """
        if stats is None:
            stats = RedisFuncCache.Stats()
        token = self._stats.set(stats)
        try:
            yield stats
        finally:
            self._stats.reset(token)
