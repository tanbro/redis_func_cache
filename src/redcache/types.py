from __future__ import annotations

import json
import weakref
from functools import wraps
from inspect import isawaitable
from itertools import chain
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional, Sequence, Tuple, Type, TypeVar, Union

from redis import Redis
from redis.commands.core import Script

from .constants import DEFAULT_MAXSIZE, DEFAULT_PREFIX
from .utils import read_lua_file

if TYPE_CHECKING:
    from redis.typing import EncodableT, KeyT

FT = TypeVar("FT", bound=Callable)

__all__ = ["RedCache", "AbstractPolicy"]


class RedCache:
    def __init__(
        self,
        name: str,
        policy: Optional[Type[AbstractPolicy]] = None,
        *,
        prefix: Optional[str] = None,
        redis_client: Optional[Redis] = None,
        redis_factory: Optional[Callable[[], Redis]] = None,
        maxsize: Optional[int] = None,
        ttl: Optional[int] = None,
        retval_serializer: Optional[Callable[[Any], Union[bytes, str]]] = None,
        retval_deserializer: Optional[Callable[[Union[bytes, str]], Any]] = None,
    ):
        self._name = name
        self._policy_type = policy
        self._policy_instance: Optional[AbstractPolicy] = None
        self._prefix = prefix or DEFAULT_PREFIX
        if redis_client is None and redis_factory is None:
            raise ValueError("Either `redis_client` or `redis_factory` must be provided.")
        if redis_client is not None and redis_factory is not None:
            raise ValueError("Only one of `redis_client` and `redis_factory` could be be provided.")
        self._redis_client = redis_client
        self._redis_factory = redis_factory
        self._maxsize = maxsize
        self._ttl = ttl
        self._user_retval_serializer = retval_serializer
        self._user_retval_deserializer = retval_deserializer

    """
    Args:
        name: The name of the cache manager.
        policy: The class for the caching policy, which must inherit from AbstractPolicy.
        prefix: The prefix for cache keys. If not provided, the default prefix will be used.
        redis_client: An instance of the Redis client, default is None.
        redis_factory: A factory function to generate an instance of the Redis client, default is None.
        maxsize: The maximum size of the cache. If not provided, the default prefix will be used. Zero or negative values means no limit.
        ttl: The time-to-live (in seconds) for cache items. If not provided, the default prefix will be used. Zero or negative values means no set ttl.
        retval_serializer: A function to serialize cache items, default is None.
        retval_deserializer: A function to deserialize cache items, default is None.
    """

    @property
    def name(self) -> str:
        return self._name

    @property
    def prefix(self) -> str:
        return self._prefix

    def set_policy_type(self, policy_type: Type[AbstractPolicy]):
        if self._policy_instance is not None:
            raise ValueError("Policy instance already initialized.")
        self._policy_type = policy_type

    @property
    def policy(self) -> AbstractPolicy:
        """**It returns an instance, NOT type/class**"""
        if self._policy_instance is None:
            if self._policy_type is None:
                raise ValueError("Policy type must be provided.")
            self._policy_instance = self._policy_type(weakref.proxy(self))
        return self._policy_instance

    def get_redis_client(self) -> Redis:
        if self._redis_client:
            return self._redis_client
        if self._redis_factory:
            return self._redis_factory()
        raise RuntimeError("No redis client or factory provided.")

    @property
    def maxsize(self) -> int:
        return DEFAULT_MAXSIZE if self._maxsize is None else self._maxsize

    @property
    def ttl(self) -> int:
        return DEFAULT_MAXSIZE if self._ttl is None else self._ttl

    def serialize_retval(self, retval: Any) -> Union[bytes, str]:
        if self._user_retval_serializer:
            return self._user_retval_serializer(retval)
        return json.dumps(retval)

    def deserialize_retval(self, data: Union[bytes, str]) -> Any:
        if self._user_retval_deserializer:
            return self._user_retval_deserializer(data)
        return json.loads(data)

    def decorator(self, f: Callable, /, **kwargs):
        @wraps(f)
        def wrapper(*f_args, **f_kwargs):
            get_script, put_script = self.policy.lua_scripts
            keys = self.policy.calculate_keys(f, f_args, f_kwargs)
            hash = self.policy.calculate_hash(f, f_args, f_kwargs)
            ext_args = self.policy.calculate_ext_args(f, f_args, f_kwargs) or ()
            # 读取缓存
            cached_retval = get_script(keys=keys, args=chain((self.ttl, hash), ext_args))
            if isawaitable(cached_retval):
                raise RuntimeError("cached return value could not be an asynchronous function.")
            if cached_retval is not None:
                return self.deserialize_retval(cached_retval)
            # 缓存没有取到值，需执行函数了！
            retval = f(*f_args, **f_kwargs)
            serialized_retval = self.serialize_retval(retval)
            put_script(keys=keys, args=chain((self.maxsize, self.ttl, hash, serialized_retval), ext_args))
            return retval

        return wrapper

    def decorate(self, user_function: Optional[FT] = None, /, **kwargs) -> FT:
        if user_function is None:
            return self.decorator  # type: ignore
        elif callable(user_function):
            return self.decorator(user_function, **kwargs)  # type: ignore
        raise TypeError(f"Argument {user_function=} is not callable")

    __call__ = decorate


class AbstractPolicy:
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

    def purge(self) -> Optional[int]:
        raise NotImplementedError()

    def calculate_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Sequence[KeyT]:
        raise NotImplementedError()

    def calculate_hash(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> str:
        raise NotImplementedError()

    def calculate_ext_args(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Optional[Iterable[EncodableT]]:
        return None

    def read_lua_scripts(self) -> Tuple[str, str]:
        return read_lua_file(self.__scripts__[0]), read_lua_file(self.__scripts__[1])

    @property
    def lua_scripts(self) -> Tuple[Script, Script]:
        if self._lua_scripts is None:
            script_texts = self.read_lua_scripts()
            rc = self.cache.get_redis_client()
            self._lua_scripts = rc.register_script(script_texts[0]), rc.register_script(script_texts[1])
        return self._lua_scripts
