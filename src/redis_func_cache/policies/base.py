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

from ..cache import RedisFuncCache
from ..typing import is_async_redis_client, is_sync_redis_client
from ..utils import b64digest, get_callable_bytecode
from .abstract import AbstractPolicy

if TYPE_CHECKING:  # pragma: no cover
    pass

__all__ = ("BaseSinglePolicy", "BaseClusterSinglePolicy", "BaseMultiplePolicy", "BaseClusterMultiplePolicy")


class BaseSinglePolicy(AbstractPolicy):
    """
    Base policy for a single sorted-set or hash-map key pair.

    All decorated functions using this policy share the same Redis key pair.

    Not intended for direct use.
    """

    __key__: str

    @override
    def __init__(self, cache: CallableProxyType[RedisFuncCache]):
        if not isinstance(cache, CallableProxyType) or not bool(cache):
            raise TypeError("The 'cache' parameter must be a valid weak reference proxy to a RedisFuncCache instance.")
        super().__init__(cache)
        self._keys: Optional[Tuple[str, str]] = None

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Return the static Redis key pair for this cache policy.

        Returns:
            Tuple of (sorted set key, hash map key).
        """
        if self._keys is None:
            k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}"
            self._keys = f"{k}:0", f"{k}:1"
        return self._keys

    @override
    def purge(self) -> int:
        """
        Delete the cache's Redis keys synchronously.

        Returns:
            Number of keys deleted.
        """
        client = self.cache.client
        if not is_sync_redis_client(client):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        return client.delete(*self.calc_keys())

    @override
    async def apurge(self) -> int:
        """
        Delete the cache's Redis keys asynchronously.

        Returns:
            Number of keys deleted.
        """
        client = self.cache.client
        if not is_async_redis_client(client):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        return await client.delete(*self.calc_keys())  # type: ignore[union-attr]

    @override
    def get_size(self) -> int:
        """
        Get the number of items in the cache synchronously.

        Returns:
            Number of items in the cache.
        """
        client = self.cache.client
        if not is_sync_redis_client(client):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        return client.hlen(self.calc_keys()[1])

    @override
    async def aget_size(self) -> int:
        """
        Get the number of items in the cache asynchronously.

        Returns:
            Number of items in the cache.
        """
        client = self.cache.client
        if not is_async_redis_client(client):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        keys = self.calc_keys()
        return await client.hlen(keys[1])  # type: ignore[union-attr, return-value]


class BaseClusterSinglePolicy(BaseSinglePolicy):
    """
    Base policy for a single sorted-set or hash-map key pair with Redis cluster support.

    All decorated functions using this policy share the same Redis key pair.

    Not intended for direct use.
    """

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Return the static Redis key pair for this cache policy, using cluster hash tags.

        Returns:
            Tuple of (sorted set key, hash map key).
        """
        if self._keys is None:
            k = f"{self.cache.prefix}{{{self.cache.name}:{self.__key__}}}"
            self._keys = f"{k}:0", f"{k}:1"
        return self._keys


class BaseMultiplePolicy(AbstractPolicy):
    """
    Base policy for multiple sorted-set or hash-map key pairs.

    Each decorated function using this policy has its own Redis key pair.

    Not intended for direct use.
    """

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Calculate a unique Redis key pair for the given function.

        Args:
            f: The decorated function.

        Returns:
            Tuple of (sorted set key, hash map key).
        """
        if not callable(f):
            raise TypeError("Can not calculate hash for a non-callable object")
        fullname = f"{f.__module__}:{f.__qualname__}"
        h = hashlib.md5(fullname.encode())
        h.update(get_callable_bytecode(f))
        checksum = b64digest(h).decode()
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{checksum}"
        return f"{k}:0", f"{k}:1"

    @override
    def purge(self) -> int:
        """
        Delete all Redis keys for this policy synchronously.

        Returns:
            Number of keys deleted.
        """
        client = self.cache.client
        if not is_sync_redis_client(client):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        if keys := client.keys(pat):
            return client.delete(*keys)
        return 0

    @override
    async def apurge(self) -> int:
        """
        Delete all Redis keys for this policy asynchronously.

        Returns:
            Number of keys deleted.
        """
        client = self.cache.client
        if not is_async_redis_client(client):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        if keys := await client.keys(pat):  # type: ignore[union-attr]
            return await client.delete(*keys)  # type: ignore[union-attr]
        return 0


class BaseClusterMultiplePolicy(BaseMultiplePolicy):
    """
    Base policy for multiple sorted-set or hash-map key pairs with Redis cluster support.

    Each decorated function using this policy has its own Redis key pair.

    Not intended for direct use.
    """

    @override
    def calc_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Calculate a unique Redis key pair for the given function, using cluster hash tags.

        Args:
            f: The decorated function.

        Returns:
            Tuple of (sorted set key, hash map key).
        """
        if not callable(f):
            raise TypeError("Can not calculate hash for a non-callable object")
        fullname = f"{f.__module__}:{f.__qualname__}"
        h = hashlib.md5(fullname.encode())
        h.update(get_callable_bytecode(f))
        checksum = b64digest(h).decode()
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{{{checksum}}}"
        return f"{k}:0", f"{k}:1"
