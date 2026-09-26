"""Keying: the *key naming* dimension of a policy.

A :class:`Keying` object decides the Redis key pair a cached value lives under,
and enumerates/purges those keys. It is one of the three orthogonal components
composed into a :class:`~redis_func_cache.policies.Policy`:

- :class:`Keying` — how Redis keys are named
- :class:`~redis_func_cache.hashing.Hasher` — how each call is hashed to a sub-key
- :class:`~redis_func_cache.scripts.Scripts` — which Lua scripts run and how they talk to Redis

Four built-in variants cover the two orthogonal naming choices:

==================  ===========================  ===================  ====================
Class               Key pattern                  Per-function keys    Cluster support
==================  ===========================  ===================  ====================
SingleKeying        ``prefix:name:key:0|1``      no                   no
MultipleKeying      ``prefix:name:key:fn#h:0|1`` yes                  no
ClusterSingleKeying ``prefix{name:key}:0|1``     no                   yes
ClusterMultipleKeying ``...:fn{#h}:0|1``         yes                  yes
==================  ===========================  ===================  ====================

``key`` is the policy's key-name component (e.g. ``"lru"``, ``"lru-cm"``).

Keying instances are stateless and shareable: every method takes the bound
``(prefix, name)`` namespace explicitly, supplied by the owning
:class:`~redis_func_cache.policies.Policy`.

.. versionchanged:: 1.0
    Replaces the ``policies.base`` class hierarchy; key naming is now a
    composed component instead of the MRO base of every policy.
"""

from __future__ import annotations

import sys
from abc import ABC
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any

if sys.version_info < (3, 12):  # pragma: no cover
    from typing_extensions import override
else:  # pragma: no cover
    from typing import override

from .fingerprint import hash_fingerprint
from .utils import b64digest, calculate_callable_fullname

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import AsyncIterator

    from .typing import KeyNameT, RedisAsyncClientT, RedisSyncClientT

__all__ = (
    "ClusterMultipleKeying",
    "ClusterSingleKeying",
    "Keying",
    "MultipleKeying",
    "SingleKeying",
)


def _hash_key_of(index_key: str | bytes) -> str | bytes:
    """Derive the hash-map key ("...:1") from an index key ("...:0") produced by a pattern scan."""
    if isinstance(index_key, bytes):
        return index_key[:-2] + b":1"
    return index_key[:-2] + ":1"


class Keying(ABC):
    """Decide the Redis key pair a cached value lives under, and manage those keys.

    This class is designed for subclassing: :meth:`calc_key_pair` is the public API
    (kept final here) and :meth:`base_key` is the single override point. The
    ``:0``/``:1`` suffixes applied by :meth:`calc_key_pair` are an invariant every
    variant shares.
    """

    key: str
    """The policy's key-name component, embedded in every Redis key."""

    __slots__ = ()

    def base_key(self, prefix: str, name: str, fn: Callable | None = None) -> str:
        """Build the key base — everything before the ``:0``/``:1`` suffix.

        The single override point for key-naming variants. Callers should use
        :meth:`calc_key_pair`, which applies the shared ``:0``/``:1`` suffixes.

        Args:
            prefix: The cache's key prefix.
            name: The cache's name.
            fn: The function being cached. Ignored by the single variants,
                whose key pair is static; required by the multiple variants,
                which derive the pair from the function's identity.

        Returns:
            The key base without suffix.
        """
        raise NotImplementedError

    def calc_key_pair(
        self,
        prefix: str,
        name: str,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Return the ``(index key, value key)`` pair for the given function.

        Final template method: delegates the naming to :meth:`base_key` and
        applies the ``:0``/``:1`` suffixes shared by every variant.

        Args:
            prefix: The cache's key prefix.
            name: The cache's name.
            fn: The function being cached.
            args: Positional arguments (unused by the built-in variants).
            kwds: Keyword arguments (unused by the built-in variants).

        Returns:
            Tuple of (index key, value key), suffixed ``:0`` and ``:1``.
        """
        k = self.base_key(prefix, name, fn)
        return f"{k}:0", f"{k}:1"

    def iterate_key_pairs(
        self, redis_client: RedisSyncClientT, prefix: str, name: str
    ) -> Iterator[tuple[KeyNameT, KeyNameT]]:
        """Iterate over the ``(index key, value key)`` pairs owned by this policy (sync).

        Streams lazily; nothing is materialized. The base implementation yields
        the single static pair (the single-variant behavior); the multiple
        variants override this with a ``SCAN`` stream.

        Used by :meth:`Policy.vacuum` and :meth:`Policy.get_size`; the caller
        has already guarded the client.
        """
        yield self.calc_key_pair(prefix, name)

    async def aiterate_key_pairs(
        self, redis_client: RedisAsyncClientT, prefix: str, name: str
    ) -> AsyncIterator[tuple[KeyNameT, KeyNameT]]:
        """Async version of :meth:`iterate_key_pairs`."""
        yield self.calc_key_pair(prefix, name)

    def purge(self, redis_client: RedisSyncClientT, prefix: str, name: str, batch_size: int = 500) -> int:
        """Delete all Redis keys owned by this policy (sync).

        Args:
            redis_client: A synchronous redis client.
            prefix: The cache's key prefix.
            name: The cache's name.
            batch_size: The number of keys per deletion command.

        Returns:
            Number of keys deleted.
        """
        return redis_client.delete(*self.calc_key_pair(prefix, name))

    async def apurge(self, redis_client: RedisAsyncClientT, prefix: str, name: str, batch_size: int = 500) -> int:
        """Async version of :meth:`purge`."""
        return await redis_client.delete(*self.calc_key_pair(prefix, name))


class SingleKeying(Keying):
    """One static key pair shared by every decorated function; no cluster hash tags."""

    __slots__ = ("key",)

    def __init__(self, key: str) -> None:
        self.key = key

    @override
    def base_key(self, prefix: str, name: str, fn: Callable | None = None) -> str:
        return f"{prefix}{name}:{self.key}"


class ClusterSingleKeying(SingleKeying):
    """One static key pair shared by every decorated function, with a cluster hash tag."""

    __slots__ = ()

    @override
    def base_key(self, prefix: str, name: str, fn: Callable | None = None) -> str:
        return f"{prefix}{{{name}:{self.key}}}"


class MultipleKeying(Keying):
    """One key pair per decorated function; no cluster hash tags."""

    __slots__ = ("key",)

    def __init__(self, key: str) -> None:
        self.key = key

    @override
    def base_key(self, prefix: str, name: str, fn: Callable | None = None) -> str:
        if fn is None:
            raise TypeError("The multiple keying variants require the decorated function to derive the key pair")
        fullname = calculate_callable_fullname(fn)
        checksum = b64digest(hash_fingerprint("md5", True, fn)).decode()
        return f"{prefix}{name}:{self.key}:{fullname}#{checksum}"

    @override
    def iterate_key_pairs(
        self, redis_client: RedisSyncClientT, prefix: str, name: str
    ) -> Iterator[tuple[KeyNameT, KeyNameT]]:
        for k in redis_client.scan_iter(match=self._index_pattern(prefix, name)):
            yield k, _hash_key_of(k)

    @override
    async def aiterate_key_pairs(
        self, redis_client: RedisAsyncClientT, prefix: str, name: str
    ) -> AsyncIterator[tuple[KeyNameT, KeyNameT]]:
        async for k in redis_client.scan_iter(match=self._index_pattern(prefix, name)):
            yield k, _hash_key_of(k)

    @override
    def purge(self, redis_client: RedisSyncClientT, prefix: str, name: str, batch_size: int = 500) -> int:
        """Enumerate keys with ``SCAN`` and delete them in batches with ``UNLINK``."""
        pat = f"{prefix}{name}:{self.key}:*"
        removed = 0
        batch: list[KeyNameT] = []
        for key in redis_client.scan_iter(match=pat):  # type: ignore[union-attr]
            batch.append(key)
            if len(batch) >= batch_size:
                removed += redis_client.unlink(*batch)
                batch.clear()
        if batch:
            removed += redis_client.unlink(*batch)
        return removed

    @override
    async def apurge(self, redis_client: RedisAsyncClientT, prefix: str, name: str, batch_size: int = 500) -> int:
        pat = f"{prefix}{name}:{self.key}:*"
        removed = 0
        batch: list[KeyNameT] = []
        async for key in redis_client.scan_iter(match=pat):  # type: ignore[union-attr]
            batch.append(key)
            if len(batch) >= batch_size:
                removed += await redis_client.unlink(*batch)
                batch.clear()
        if batch:
            removed += await redis_client.unlink(*batch)
        return removed

    def _index_pattern(self, prefix: str, name: str) -> str:
        return f"{prefix}{name}:{self.key}:*:0"


class ClusterMultipleKeying(MultipleKeying):
    """One key pair per decorated function, with a cluster hash tag around the checksum."""

    __slots__ = ()

    @override
    def base_key(self, prefix: str, name: str, fn: Callable | None = None) -> str:
        if fn is None:
            raise TypeError("The multiple keying variants require the decorated function to derive the key pair")
        fullname = calculate_callable_fullname(fn)
        checksum = b64digest(hash_fingerprint("md5", True, fn)).decode()
        return f"{prefix}{name}:{self.key}:{fullname}#{{{checksum}}}"
