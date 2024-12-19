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

import redis
import redis.asyncio
from redis.commands.core import AsyncScript, Script

from .constants import DEFAULT_MAXSIZE, DEFAULT_PREFIX, DEFAULT_TTL
from .policies.abstract import AbstractPolicy

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, EncodedT, KeyT

    FT = TypeVar("FT", bound=Callable)
    SerializerT = Callable[[Any], EncodedT]
    DeserializerT = Callable[[EncodedT], Any]


__all__ = ("RedisFuncCache",)

RedisClientT = TypeVar("RedisClientT", bound=Union[redis.Redis, redis.asyncio.Redis])


class RedisFuncCache(Generic[RedisClientT]):
    def __init__(
        self,
        name: str,
        policy: Type[AbstractPolicy],
        client: Union[RedisClientT, Callable[[], RedisClientT]],
        maxsize: Optional[int] = None,
        ttl: Optional[int] = None,
        prefix: Optional[str] = None,
        serializer: Union[Tuple[SerializerT, DeserializerT], None] = None,
    ):
        """Initializes the Cache instance with the given parameters.

        Args:
            name: The name of the cache manager.

                It is assigned to property :meth:`.name`.

            policy: The class for the caching policy

            client: Redis client to use.

                - You can pass either a :class:`redis.Redis` or a :class:`redis.asyncio.Redis` object, or a function that returns one of these objects.

                - Access the client via the :meth:`.client` property.

                .. note::
                    If a function is provided, it will be executed **every time** the :meth:`.client` property is accessed.

            maxsize: The maximum size of the cache.

                If not provided, the default is :data:`.DEFAULT_MAXSIZE`.
                Zero or negative values means no limit.
                Assigned to property :meth:`.maxsize`.

            ttl: The time-to-live (in seconds) for cache items.

                If not provided, the default is :data:`.DEFAULT_TTL`.
                Zero or negative values means no set ttl.
                Assigned to property :meth:`.ttl`.


            prefix: The prefix for cache keys.

                If not provided, the default is :data:`.DEFAULT_PREFIX`.
                Assigned to property :meth:`.prefix`.

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
        self._redis_instance: Optional[RedisClientT] = None
        self._redis_factory: Optional[Callable[[], RedisClientT]] = None
        if isinstance(client, (redis.Redis, redis.asyncio.Redis)):
            self._redis_instance = client  # type: ignore[assignment]
        elif callable(client):
            self._redis_factory = client
        else:
            raise TypeError(
                f"client must be a redis client instance or a function that returns a redis client instance, got {type(client)} instead."
            )
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
        """
        .. tip::
            It returns an instance, NOT type/class
        """
        if self._policy_instance is None:
            self._policy_instance = self._policy_type(weakref.proxy(self))
        return self._policy_instance

    @property
    def client(self) -> RedisClientT:
        """
        Returns:
            The :class:`redis.Redis` or :class:`redis.asyncio.Redis` instance used in the cache.
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
        script: Script,
        key_pair: Tuple[KeyT, KeyT],
        hash: KeyT,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ) -> Optional[EncodedT]:
        """Execute the given redis lua script with given arguments.

        The script shall try get the return value from cache with given keys and hash.

        Returns:
            The hit return value, or :data:`None` if missing.
        """
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        return script(keys=key_pair, args=chain((ttl, hash, encoded_options), ext_args))

    @classmethod
    async def aget(
        cls,
        script: AsyncScript,
        key_pair: Tuple[KeyT, KeyT],
        hash: KeyT,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ) -> Optional[EncodedT]:
        """Async version of :meth:`.get`"""
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        return await script(keys=key_pair, args=chain((ttl, hash, encoded_options), ext_args))

    @classmethod
    def put(
        cls,
        script: Script,
        key_pair: Tuple[KeyT, KeyT],
        hash: KeyT,
        value: EncodableT,
        maxsize: int,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ):
        """Execute the given redis lua script with given arguments.

        The script shall put the return value into cache with given keys and hash.
        If the cache reached its :meth:`maxsize`, it shall remove one item according to its :meth:`policy`, before insert.
        """
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        script(keys=key_pair, args=chain((maxsize, ttl, hash, value, encoded_options), ext_args))

    @classmethod
    async def aput(
        cls,
        script: AsyncScript,
        key_pair: Tuple[KeyT, KeyT],
        hash: KeyT,
        value: EncodableT,
        maxsize: int,
        ttl: int,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ):
        """Same as :meth:`.put` but async."""
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        await script(keys=key_pair, args=chain((maxsize, ttl, hash, value, encoded_options), ext_args))

    def exec(self, user_function: Callable, user_args: Sequence, user_kwds: Mapping[str, Any], **options):
        """Execute the given user function with given arguments.

        In this method, :meth:`.get` is called before the ``user_function``, and :meth:`.put` is called afterward.
        """
        script_0, script_1 = self.policy.lua_scripts
        if not isinstance(script_0, Script) or not isinstance(script_1, Script):
            raise RuntimeError(
                f"A tuple of two {Script} objects is required for execution, but actually got ({script_0!r}, {script_1!r})."
            )
        keys = self.policy.calc_keys(user_function, user_args, user_kwds)
        hash = self.policy.calc_hash(user_function, user_args, user_kwds)
        ext_args = self.policy.calc_ext_args(user_function, user_args, user_kwds) or ()
        cached = self.get(script_0, keys, hash, self.ttl, options, ext_args)
        if cached is not None:
            return self.deserialize_return_value(cached)
        user_return_value = user_function(*user_args, **user_kwds)
        user_retval_serialized = self.serialize_return_value(user_return_value)
        self.put(script_1, keys, hash, user_retval_serialized, self.maxsize, self.ttl, options, ext_args)
        return user_return_value

    async def aexec(self, user_function: Callable, user_args: Sequence, user_kwds: Mapping[str, Any], **options):
        """Async version of :meth:`.exec`"""
        script_0, script_1 = self.policy.lua_scripts
        if not (isinstance(script_0, AsyncScript) and isinstance(script_1, AsyncScript)):
            raise RuntimeError(
                f"A tuple of two {AsyncScript} objects is required for async execution, but actually got ({script_0!r}, {script_1!r})."
            )
        keys = self.policy.calc_keys(user_function, user_args, user_kwds)
        hash = self.policy.calc_hash(user_function, user_args, user_kwds)
        ext_args = self.policy.calc_ext_args(user_function, user_args, user_kwds) or ()
        cached = await self.aget(script_0, keys, hash, self.ttl, options, ext_args)
        if cached is not None:
            return self.deserialize_return_value(cached)
        rval = user_function(*user_args, **user_kwds)
        if iscoroutine(rval):
            user_return_value = await rval
        else:
            user_return_value = rval
        user_retval_serialized = self.serialize_return_value(user_return_value)
        await self.aput(script_1, keys, hash, user_retval_serialized, self.maxsize, self.ttl, options, ext_args)
        return user_return_value

    def decorate(self, user_function: Optional[FT] = None, /, **kwargs) -> FT:
        """Decorate the given function with cache."""

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
        elif callable(user_function):
            return decorator(user_function)  # type: ignore
        raise TypeError(f"‘{self.__class__.__qualname__}’ cannot decorate {user_function!r}")

    __call__ = decorate
