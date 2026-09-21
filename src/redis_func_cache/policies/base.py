"""Base class for single-pair cache."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if sys.version_info < (3, 12):  # pragma: no cover
    from typing_extensions import override
else:  # pragma: no cover
    from typing import override


from ..fingerprint import hash_fingerprint
from ..typing import is_redis_async_client, is_redis_sync_client
from ..utils import b64digest, calculate_callable_fullname
from .abstract import AbstractPolicy

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import KeyT

    from ..typing import RedisClientT

__all__ = ("BaseClusterMultiplePolicy", "BaseClusterSinglePolicy", "BaseMultiplePolicy", "BaseSinglePolicy")


def _hash_key_of(zset_key: str | bytes) -> str | bytes:
    """Derive the hash-map key ("...:1") from a sorted-set key ("...:0") produced by a pattern scan."""
    if isinstance(zset_key, bytes):
        return zset_key[:-2] + b":1"
    return zset_key[:-2] + ":1"


class BaseSinglePolicy(AbstractPolicy):
    """
    Base policy for a single sorted-set or hash-map key pair.

    .. inheritance-diagram:: BaseSinglePolicy
        :parts: 1

    All decorated functions using this policy share the same Redis key pair.

    Not intended for direct use.
    """

    __key__: str

    @override
    def __init__(self) -> None:
        super().__init__()
        self._keys: tuple[str, str] | None = None

    @override
    def calc_keys(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
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
    def purge(self, redis_client: RedisClientT, batch_size: int = 500) -> int:
        """
        Delete the cache's Redis keys synchronously.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            batch_size: Ignored — a single policy owns exactly one static key pair,
                deleted with one command.

        Returns:
            Number of keys deleted.
        """
        if not is_redis_sync_client(redis_client):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        return redis_client.delete(*self.calc_keys())

    @override
    async def apurge(self, redis_client: RedisClientT, batch_size: int = 500) -> int:
        """
        Async version of :meth:`purge`.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            batch_size: Ignored — a single policy owns exactly one static key pair,
                deleted with one command.

        Returns:
            Number of keys deleted.
        """
        if not is_redis_async_client(redis_client):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        return await redis_client.delete(*self.calc_keys())  # type: ignore[union-attr]

    @override
    def get_size(self, redis_client: RedisClientT) -> int:
        """
        Get the number of items in the cache synchronously.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.

        Returns:
            Number of items in the cache.
        """
        if not is_redis_sync_client(redis_client):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        return redis_client.hlen(self.calc_keys()[1])

    @override
    async def aget_size(self, redis_client: RedisClientT) -> int:
        """
        Get the number of items in the cache asynchronously.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.

        Returns:
            Number of items in the cache.
        """
        if not is_redis_async_client(redis_client):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        keys = self.calc_keys()
        return await redis_client.hlen(keys[1])  # type: ignore[union-attr, return-value]

    @override
    def calc_key_pairs(self, redis_client: RedisClientT) -> list[tuple[KeyT, KeyT]]:
        return [self.calc_keys()]

    @override
    async def acalc_key_pairs(self, redis_client: RedisClientT) -> list[tuple[KeyT, KeyT]]:
        return [self.calc_keys()]


class BaseClusterSinglePolicy(BaseSinglePolicy):
    """
    Base policy for a single sorted-set or hash-map key pair with Redis cluster support.

    .. inheritance-diagram:: BaseClusterSinglePolicy
        :parts: 1

    All decorated functions using this policy share the same Redis key pair.

    Not intended for direct use.
    """

    @override
    def calc_keys(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
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

    .. inheritance-diagram:: BaseMultiplePolicy
        :parts: 1

    Each decorated function using this policy has its own Redis key pair.

    Not intended for direct use.
    """

    @override
    def calc_keys(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """
        Calculate a unique Redis key pair for the given function.

        Args:
            fn: The decorated function.

        Returns:
            Tuple of (sorted set key, hash map key).
        """
        if fn is None:
            raise TypeError("Can not calculate hash for None")
        fullname = calculate_callable_fullname(fn)
        checksum = b64digest(hash_fingerprint("md5", True, fn)).decode()
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{checksum}"
        return f"{k}:0", f"{k}:1"

    @override
    def purge(self, redis_client: RedisClientT, batch_size: int = 500) -> int:
        """
        Delete all Redis keys for this policy synchronously.

        Keys are enumerated with `SCAN` (never the blocking `KEYS`) and deleted
        in batches with `UNLINK`, so the Redis server stays responsive regardless
        of how many key pairs this policy owns.

        Args:
            batch_size: The number of keys per deletion command.

        Returns:
            Number of keys deleted.

        .. versionadded:: TODO
            The *batch_size* parameter.
        """
        if not is_redis_sync_client(redis_client):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        removed = 0
        batch: list[KeyT] = []
        for key in redis_client.scan_iter(match=pat):  # type: ignore[union-attr]
            batch.append(key)
            if len(batch) >= batch_size:
                removed += redis_client.unlink(*batch)
                batch.clear()
        if batch:
            removed += redis_client.unlink(*batch)
        return removed

    @override
    async def apurge(self, redis_client: RedisClientT, batch_size: int = 500) -> int:
        """
        Async version of :meth:`purge`.

        Args:
            batch_size: The number of keys per deletion command.

        Returns:
            Number of keys deleted.

        .. versionadded:: TODO
            The *batch_size* parameter.
        """
        if not is_redis_async_client(redis_client):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        removed = 0
        batch: list[KeyT] = []
        async for key in redis_client.scan_iter(match=pat):  # type: ignore[union-attr]
            batch.append(key)
            if len(batch) >= batch_size:
                removed += await redis_client.unlink(*batch)  # type: ignore[union-attr]
                batch.clear()
        if batch:
            removed += await redis_client.unlink(*batch)  # type: ignore[union-attr]
        return removed

    @override
    def calc_key_pairs(self, redis_client: RedisClientT) -> list[tuple[KeyT, KeyT]]:
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*:0"
        return [(zset_key, _hash_key_of(zset_key)) for zset_key in redis_client.scan_iter(match=pat)]  # type: ignore[union-attr]

    @override
    async def acalc_key_pairs(self, redis_client: RedisClientT) -> list[tuple[KeyT, KeyT]]:
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*:0"
        return [(zset_key, _hash_key_of(zset_key)) async for zset_key in redis_client.scan_iter(match=pat)]  # type: ignore[union-attr]

    @override
    def get_size(self, redis_client: RedisClientT) -> int:
        """
        Get the total number of cached items across all decorated functions.

        Multiple policies hold one key pair per decorated function; the reported
        size is the sum of the hash lengths of every key pair.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.

        Returns:
            Total number of items in the cache.
        """
        if not is_redis_sync_client(redis_client):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*:1"
        return sum(redis_client.hlen(hmap_key) for hmap_key in redis_client.scan_iter(match=pat))  # type: ignore[union-attr]

    @override
    async def aget_size(self, redis_client: RedisClientT) -> int:
        """Async version of :meth:`get_size`."""
        if not is_redis_async_client(redis_client):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*:1"
        total = 0
        async for hmap_key in redis_client.scan_iter(match=pat):  # type: ignore[union-attr]
            total += await redis_client.hlen(hmap_key)  # type: ignore[union-attr]
        return total


class BaseClusterMultiplePolicy(BaseMultiplePolicy):
    """
    Base policy for multiple sorted-set or hash-map key pairs with Redis cluster support.

    .. inheritance-diagram:: BaseClusterMultiplePolicy
        :parts: 1

    Each decorated function using this policy has its own Redis key pair.

    Not intended for direct use.
    """

    @override
    def calc_keys(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """
        Calculate a unique Redis key pair for the given function, using cluster hash tags.

        Args:
            fn: The decorated function.

        Returns:
            Tuple of (sorted set key, hash map key).
        """
        if fn is None:
            raise TypeError("Can not calculate hash for None")
        fullname = calculate_callable_fullname(fn)
        checksum = b64digest(hash_fingerprint("md5", True, fn)).decode()
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{{{checksum}}}"
        return f"{k}:0", f"{k}:1"
