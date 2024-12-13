from __future__ import annotations

import json
import weakref
from functools import wraps
from inspect import isawaitable
from itertools import chain
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union

from redis import Redis
from redis.commands.core import Script

if TYPE_CHECKING:
    from redis.typing import EncodableT, EncodedT, KeyT

from .constants import DEFAULT_MAXSIZE, DEFAULT_PREFIX
from .utils import read_lua_file

FT = TypeVar("FT", bound=Callable)

__all__ = ["RedCache", "AbstractPolicy"]


class RedCache:
    def __init__(
        self,
        name: str,
        policy: Type[AbstractPolicy],
        *,
        prefix: Optional[str] = None,
        redis: Optional[Redis] = None,
        redis_factory: Optional[Callable[[], Redis]] = None,
        maxsize: Optional[int] = None,
        ttl: Optional[int] = None,
        serializer: Union[Tuple[Callable[[Any], EncodedT], Callable[[EncodedT], Any]], None] = None,
    ):
        """
        Args:
            name: The name of the cache manager.
            policy: The class for the caching policy, which must inherit from AbstractPolicy.
            prefix: The prefix for cache keys. If not provided, the default value will be used.
            redis: An instance of the Redis client, default is None.
            redis_factory: A factory function to generate an instance of the Redis client, default is None.
            maxsize: The maximum size of the cache. If not provided, the default value will be used. Zero or negative values means no limit.
            ttl: The time-to-live (in seconds) for cache items. If not provided, the default value will be used. Zero or negative values means no set ttl.
            serializer: Optional serialize/deserialize function pair for return value of what decorated. Default/`None` means to use meth:`json.dumps` and meth:`json.loads`.
        """
        self._name = name
        self._policy_type = policy
        self._policy_instance: Optional[AbstractPolicy] = None
        self._prefix = prefix or DEFAULT_PREFIX
        if redis is None and redis_factory is None:
            raise ValueError("Either `redis` or `redis_factory` is required.")
        if redis is not None and redis_factory is not None:
            raise ValueError("Only one of `redis` and `redis_factory` could be provided.")
        self._redis = redis
        self._redis_factory = redis_factory
        self._maxsize = maxsize
        self._ttl = ttl
        self._user_return_value_serializer = serializer[0] if serializer else None
        self._user_return_value_deserializer = serializer[1] if serializer else None

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
        return DEFAULT_MAXSIZE if self._maxsize is None else self._maxsize

    @property
    def ttl(self) -> int:
        return DEFAULT_MAXSIZE if self._ttl is None else self._ttl

    def serialize_return_value(self, retval: Any) -> EncodedT:
        if self._user_return_value_serializer:
            return self._user_return_value_serializer(retval)
        return json.dumps(retval, ensure_ascii=False).encode()

    def deserialize_return_value(self, data: EncodedT) -> Any:
        if self._user_return_value_deserializer:
            return self._user_return_value_deserializer(data)
        return json.loads(data)

    def exec_get_script(self, keys: Sequence[KeyT], args: Iterable[EncodableT]):
        return self.policy.lua_scripts[0](keys, args)

    def exec_put_script(self, keys: Sequence[KeyT], args: Iterable[EncodableT]):
        return self.policy.lua_scripts[1](keys, args)

    def decorator(self, f: Callable, /, **kwargs):
        @wraps(f)
        def wrapper(*f_args, **f_kwargs):
            keys = self.policy.calc_keys(f, f_args, f_kwargs)
            hash = self.policy.calc_hash(f, f_args, f_kwargs)
            ext_args = self.policy.calc_ext_args(f, f_args, f_kwargs) or ()
            cached_retval = self.exec_get_script(keys=keys, args=chain((self.ttl, hash), ext_args))
            if isawaitable(cached_retval):
                raise RuntimeError("cached return value could not be an asynchronous function.")  # pragma: no cover
            if cached_retval is not None:
                return self.deserialize_return_value(cached_retval)
            retval = f(*f_args, **f_kwargs)
            retval_ser = self.serialize_return_value(retval)
            self.exec_put_script(keys=keys, args=chain((self.maxsize, self.ttl, hash, retval_ser), ext_args))
            return retval

        return wrapper

    def decorate(self, user_function: Optional[FT] = None, /, **kwargs) -> FT:
        if user_function is None:
            return self.decorator  # type: ignore
        elif callable(user_function):
            return self.decorator(user_function, **kwargs)  # type: ignore
        raise TypeError(f"Argument {user_function=} is not callable")  # pragma: no cover

    __call__ = decorate


class AbstractPolicy:
    __key__: str
    __scripts__: Tuple[str, str]

    def __init__(self, cache: weakref.CallableProxyType[RedCache]):
        self._cache = cache
        self._lua_scripts: Optional[Tuple[Script, Script]] = None

    @property
    def cache(self) -> RedCache:
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
