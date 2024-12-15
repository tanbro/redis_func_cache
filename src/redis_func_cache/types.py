from __future__ import annotations

import json
import weakref
from functools import wraps
from itertools import chain
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union

from redis import Redis

if TYPE_CHECKING:
    from redis.commands.core import Script
    from redis.typing import EncodableT, EncodedT, KeyT

    UserFunctionT = TypeVar("UserFunctionT", bound=Callable)
    SerializerT = Callable[[Any], EncodedT]
    DeserializerT = Callable[[EncodedT], Any]

from .constants import DEFAULT_MAXSIZE, DEFAULT_PREFIX, DEFAULT_TTL
from .utils import read_lua_file

__all__ = ["RedisFuncCache", "AbstractPolicy"]


class RedisFuncCache:
    def __init__(
        self,
        name: str,
        policy: Type[AbstractPolicy],
        redis: Union[str, Redis, Callable[[], Redis]],
        prefix: Optional[str] = None,
        maxsize: Optional[int] = None,
        ttl: Optional[int] = None,
        serializer: Union[Tuple[SerializerT, DeserializerT], None] = None,
    ):
        """
        Args:
            name: The name of the cache manager.
            policy: The class for the caching policy, which must inherit from AbstractPolicy.
            prefix: The prefix for cache keys. If not provided, the default value is :const:`DEFAULT_PREFIX`.
            redis: Redis client to use.
            maxsize: The maximum size of the cache. If not provided, the default :const:`DEFAULT_MAXSIZE` will be used. Zero or negative values means no limit.
            ttl: The time-to-live (in seconds) for cache items. If not provided, the default value :const:`DEFAULT_TTL` will be used. Zero or negative values means no set ttl.
            serializer: Optional serialize/deserialize function pair for return value of what decorated. Default/`None` means to use meth:`json.dumps` and meth:`json.loads`.
        """
        self._name = name
        self._policy_type = policy
        self._policy_instance: Optional[AbstractPolicy] = None
        self._prefix = prefix or DEFAULT_PREFIX
        self._redis: Optional[Redis] = None
        self._redis_factory: Optional[Callable[[], Redis]] = None
        if isinstance(redis, str):
            self._redis = Redis.from_url(redis)
        elif isinstance(redis, Redis):
            self._redis = redis
        elif callable(redis):
            self._redis_factory = redis
        else:
            raise TypeError("redis must be a string, a Redis instance, or a function returns Redis instance.")
        self._maxsize = DEFAULT_MAXSIZE if maxsize is None else int(maxsize)
        self._ttl = DEFAULT_TTL if ttl is None else int(ttl)
        self._user_return_value_serializer: Optional[SerializerT] = serializer[0] if serializer else None
        self._user_return_value_deserializer: Optional[DeserializerT] = serializer[1] if serializer else None

    @property
    def name(self) -> str:
        return self._name

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def policy(self) -> AbstractPolicy:
        """**It returns an instance, NOT type/class**"""
        if self._policy_instance is None:
            self._policy_instance = self._policy_type(weakref.proxy(self))
        return self._policy_instance

    def get_redis_client(self) -> Redis:
        if self._redis:
            return self._redis
        if self._redis_factory:
            return self._redis_factory()
        raise RuntimeError("No redis client or factory provided.")

    @property
    def redis_client(self) -> Redis:
        return self.get_redis_client()

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def ttl(self) -> int:
        return self._ttl

    def serialize_return_value(self, value: Any) -> EncodedT:
        if self._user_return_value_serializer:
            return self._user_return_value_serializer(value)
        return json.dumps(value, ensure_ascii=False).encode()

    def deserialize_return_value(self, data: EncodedT) -> Any:
        if self._user_return_value_deserializer:
            return self._user_return_value_deserializer(data)
        return json.loads(data)

    @classmethod
    def get(
        cls,
        script: Script,
        key_pair: Tuple[KeyT, KeyT],
        hash: KeyT,
        ttl: Optional[int] = None,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ) -> EncodedT:
        ttl = DEFAULT_TTL if ttl is None else ttl
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        return script(keys=key_pair, args=chain((ttl, hash, encoded_options), ext_args))

    @classmethod
    def put(
        cls,
        script: Script,
        key_pair: Tuple[KeyT, KeyT],
        hash: KeyT,
        value: EncodableT,
        maxsize: Optional[int] = None,
        ttl: Optional[int] = None,
        options: Optional[Mapping[str, Any]] = None,
        ext_args: Optional[Iterable[EncodableT]] = None,
    ):
        maxsize = DEFAULT_MAXSIZE if maxsize is None else maxsize
        ttl = DEFAULT_TTL if ttl is None else ttl
        encoded_options = json.dumps(options or {}, ensure_ascii=False).encode()
        ext_args = ext_args or ()
        script(keys=key_pair, args=chain((maxsize, ttl, hash, value, encoded_options), ext_args))

    def exec_user_function(self, user_function: Callable, user_args: Sequence, user_kwds: Mapping[str, Any], **options):
        keys = self.policy.calc_keys(user_function, user_args, user_kwds)
        hash = self.policy.calc_hash(user_function, user_args, user_kwds)
        ext_args = self.policy.calc_ext_args(user_function, user_args, user_kwds) or ()
        cached = self.get(self.policy.lua_scripts[0], keys, hash, self.ttl, options, ext_args)
        if cached is not None:
            if not isinstance(cached, (bytes, str, memoryview)):
                raise ValueError("Cached value is not bytes/str/memoryview type.")
            return self.deserialize_return_value(cached)
        user_return_value = user_function(*user_args, **user_kwds)
        user_retval_serialized = self.serialize_return_value(user_return_value)
        self.put(
            self.policy.lua_scripts[1], keys, hash, user_retval_serialized, self.maxsize, self.ttl, options, ext_args
        )
        return user_return_value

    def decorate(self, user_function: Optional[UserFunctionT] = None, /, **kwargs) -> UserFunctionT:
        def decorator(f: UserFunctionT):
            @wraps(f)
            def wrapper(*f_args, **f_kwargs):
                return self.exec_user_function(f, f_args, f_kwargs, **kwargs)

            return wrapper

        if user_function is None:
            return decorator  # type: ignore
        elif callable(user_function):
            return decorator(user_function)  # type: ignore
        raise TypeError(f"Argument {user_function=} is not callable")  # pragma: no cover

    __call__ = decorate


class AbstractPolicy:
    __key__: str
    __scripts__: Tuple[str, str]

    def __init__(self, cache: weakref.CallableProxyType[RedisFuncCache]):
        self._cache = cache
        self._lua_scripts: Optional[Tuple[Script, Script]] = None

    @property
    def cache(self) -> RedisFuncCache:
        """It's in fact a weakref proxy object, returned by:func:`weakref.proxy`.
        weakref is not a good idea.
        """
        return self._cache  # type: ignore

    def read_lua_scripts(self) -> Tuple[str, str]:
        return read_lua_file(self.__scripts__[0]), read_lua_file(self.__scripts__[1])

    @property
    def lua_scripts(self) -> Tuple[Script, Script]:
        if self._lua_scripts is None:
            script_texts = self.read_lua_scripts()
            rc = self.cache.get_redis_client()
            self._lua_scripts = rc.register_script(script_texts[0]), rc.register_script(script_texts[1])
        return self._lua_scripts

    def purge(self) -> Optional[int]:
        raise NotImplementedError()  # pragma: no cover

    def get_size(self) -> int:
        raise NotImplementedError()  # pragma: no cover

    @property
    def size(self) -> int:
        return self.get_size()

    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        raise NotImplementedError()  # pragma: no cover

    def calc_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> KeyT:
        raise NotImplementedError()  # pragma: no cover

    def calc_ext_args(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Optional[Iterable[EncodableT]]:
        return None
