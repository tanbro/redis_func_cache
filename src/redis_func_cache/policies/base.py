"""Base class for single-pair cache."""

from __future__ import annotations

import hashlib
import sys
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence, Tuple
from weakref import CallableProxyType

if sys.version_info < (3, 12):  # pragma: no cover
    from typing_extensions import override
else:  # pragma: no cover
    from typing import override


from ..cache import RedisAsyncClientTypes, RedisFuncCache, RedisSyncClientTypes
from ..utils import b64digest, get_function_code
from .abstract import AbstractPolicy

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import KeyT

__all__ = ("BaseSinglePolicy", "BaseClusterSinglePolicy", "BaseMultiplePolicy", "BaseClusterMultiplePolicy")


class BaseSinglePolicy(AbstractPolicy):
    """
    .. inheritance-diagram:: BaseSinglePolicy

    Base policy class for a single sorted-set or hash-map key pair.
    All decorated functions of this policy share the same key pair.

    This class should not be used directly.
    """

    __key__: str

    @override
    def __init__(self, cache: CallableProxyType[RedisFuncCache]):
        super().__init__(cache)
        self._keys: Optional[tuple[str, str]] = None

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        if self._keys is None:
            k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}"
            self._keys = f"{k}:0", f"{k}:1"
        return self._keys

    @override
    def purge(self) -> int:
        client = self.cache.client
        if not isinstance(client, RedisSyncClientTypes):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        return client.delete(*self.calc_keys())

    @override
    async def apurge(self) -> int:
        client = self.cache.client
        if not isinstance(client, RedisAsyncClientTypes):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        return await client.delete(*self.calc_keys())  # type: ignore[union-attr]

    @override
    def get_size(self) -> int:
        client = self.cache.client
        if not isinstance(client, RedisSyncClientTypes):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        return client.hlen(self.calc_keys()[1])

    @override
    async def aget_size(self) -> int:
        client = self.cache.client
        if not isinstance(client, RedisAsyncClientTypes):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        return await client.hlen(self.calc_keys()[1])  # type: ignore[union-attr]


class BaseClusterSinglePolicy(BaseSinglePolicy):
    """
    .. inheritance-diagram:: BaseClusterSinglePolicy

    Base policy class for a single sorted-set or hash-map key pair, with cluster support.
    All decorated functions of this policy share the same key pair.

    This class should not be used directly.
    """

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        if self._keys is None:
            k = f"{self.cache.prefix}{{{self.cache.name}:{self.__key__}}}"
            self._keys = f"{k}:0", f"{k}:1"
        return self._keys


class BaseMultiplePolicy(AbstractPolicy):
    """
    .. inheritance-diagram:: BaseMultiplePolicy

    Base policy class for multiple sorted-set or hash-map key pairs.
    Each decorated function of this policy has its own key pair.

    This class should not be used directly.
    """

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        if not callable(f):
            raise TypeError("Can not calculate hash for a non-callable object")
        fullname = f"{f.__module__}:{f.__qualname__}"
        h = hashlib.md5(fullname.encode())
        h.update(get_function_code(f))
        checksum = b64digest(h).decode()
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{checksum}"
        return f"{k}:0", f"{k}:1"

    @override
    def purge(self) -> int:
        client = self.cache.client
        if not isinstance(client, RedisSyncClientTypes):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        keys = client.keys(pat)
        if keys:
            return client.delete(*keys)
        return 0

    @override
    async def apurge(self) -> int:
        client = self.cache.client
        if not isinstance(client, RedisAsyncClientTypes):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        keys = await client.keys(pat)  # type: ignore[union-attr]
        if keys:
            return await client.delete(*keys)  # type: ignore[union-attr]
        return 0


class BaseClusterMultiplePolicy(BaseMultiplePolicy):
    """
    .. inheritance-diagram:: BaseClusterMultiplePolicy

    Base policy class for multiple sorted-set or hash-map key pairs, with cluster support.
    Each decorated function of this policy has its own key pair.

    This class should not be used directly.
    """

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        if not callable(f):
            raise TypeError("Can not calculate hash for a non-callable object")
        fullname = f"{f.__module__}:{f.__qualname__}"
        h = hashlib.md5(fullname.encode())
        h.update(get_function_code(f))
        checksum = b64digest(h).decode()
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{{{checksum}}}"
        return f"{k}:0", f"{k}:1"
