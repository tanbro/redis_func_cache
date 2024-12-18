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

import redis
import redis.asyncio

from ..cache import RedisFuncCache
from ..utils import base64_hash_digest, get_fullname, get_source
from .abstract import AbstractPolicy

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import KeyT


__all__ = ("BaseSinglePolicy", "BaseClusterSinglePolicy", "BaseMultiplePolicy", "BaseClusterMultiplePolicy")


class BaseSinglePolicy(AbstractPolicy):
    """
    Base policy class for a single sorted-set or hash-map key pair.
    All decorated functions of this policy share the same key pair.

    This class should not be used directly.

    .. inheritance-diagram:: BaseSinglePolicy
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
    def purge(self) -> Optional[int]:
        client = self.cache.client
        if not isinstance(client, redis.Redis):
            raise TypeError(
                f"Expect type of the cache object's client is {redis.Redis}, but actual type is {type(client)}"
            )
        return client.delete(*self.calc_keys())

    @override
    async def apurge(self) -> Optional[int]:
        client = self.cache.client
        if not isinstance(client, redis.asyncio.Redis):
            raise TypeError(
                f"Expect type of the cache object's client is {redis.asyncio.Redis}, but actual type is {type(client)}"
            )
        return await client.delete(*self.calc_keys())

    @override
    def size(self) -> int:
        client = self.cache.client
        if not isinstance(client, redis.Redis):
            raise TypeError(
                f"Expect type of the cache object's client is {redis.Redis}, but actual type is {type(client)}"
            )
        return client.hlen(self.calc_keys()[1])

    @override
    async def asize(self) -> int:
        client = self.cache.client
        if not isinstance(client, redis.asyncio.Redis):
            raise TypeError(
                f"Expect type of the cache object's client is {redis.Redis}, but actual type is {type(client)}"
            )
        return await client.hlen(self.calc_keys()[1])


class BaseClusterSinglePolicy(BaseSinglePolicy):
    """
    Base policy class for a single sorted-set or hash-map key pair, with cluster support.
    All decorated functions of this policy share the same key pair.

    This class should not be used directly.

    .. inheritance-diagram:: BaseClusterSinglePolicy
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
    Base policy class for multiple sorted-set or hash-map key pairs.
    Each decorated function of this policy has its own key pair.

    This class should not be used directly.

    .. inheritance-diagram:: BaseMultiplePolicy
    """

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        if not callable(f):
            raise TypeError(f"Can not calculate hash for {f=}")
        fullname = get_fullname(f)
        h = hashlib.md5(fullname.encode())
        source = get_source(f)
        if source is not None:
            h.update(source.encode())
        checksum = base64_hash_digest(h).decode()
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{checksum}"
        return f"{k}:0", f"{k}:1"

    @override
    def purge(self) -> int:
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        client = self.cache.get_client()
        if not isinstance(client, redis.Redis):
            raise TypeError(
                f"Expect type of the cache object's client is {redis.Redis}, but actual type is {type(client)}"
            )
        keys = client.keys(pat)
        if keys:
            return client.delete(*keys)
        return 0

    @override
    async def apurge(self) -> int:
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        client = self.cache.get_client()
        if not isinstance(client, redis.asyncio.Redis):
            raise TypeError(
                f"Expect type of the cache object's client is {redis.asyncio.Redis}, but actual type is {type(client)}"
            )
        keys = await client.keys(pat)
        if keys:
            return await client.delete(*keys)
        return 0


class BaseClusterMultiplePolicy(BaseMultiplePolicy):
    """
    Base policy class for multiple sorted-set or hash-map key pairs, with cluster support.
    Each decorated function of this policy has its own key pair.

    This class should not be used directly.

    .. inheritance-diagram:: BaseClusterMultiplePolicy
    """

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[KeyT, KeyT]:
        if not callable(f):
            raise TypeError(f"Can not calculate hash for {f=}")
        fullname = get_fullname(f)
        h = hashlib.md5(fullname.encode())
        source = get_source(f)
        if source is not None:
            h.update(source.encode())
        checksum = base64_hash_digest(h).decode()
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{{{checksum}}}"
        return f"{k}:0", f"{k}:1"
