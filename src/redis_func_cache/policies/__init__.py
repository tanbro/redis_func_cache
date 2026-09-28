"""Policy: the composition of keying, hashing and scripts dimensions.

A :class:`Policy` is the object a :class:`~redis_func_cache.RedisFuncCache` takes;
it composes the three orthogonal dimensions instead of weaving them through a
multiple-inheritance hierarchy:

- :class:`~redis_func_cache.keying.Keying` — how Redis keys are named
- :class:`~redis_func_cache.hashing.Hasher` — how each call is hashed to a sub-key
- :class:`~redis_func_cache.scripts.Scripts` — which Lua scripts run and what they expect

The policy is the **single entry point from the cache layer**: it computes
hashes and key pairs, invokes the Lua scripts (via the ARGV helpers in
:mod:`~redis_func_cache.scripts`), and owns the cross-key-pair maintenance
operations (``purge_all_pairs`` / ``vacuum_all_pairs`` / ``get_size``). Higher layers never talk
to :attr:`scripts` directly.

IO ownership follows each component's abstraction — Redis IO is *not*
exclusive to the policy:

- :class:`~redis_func_cache.keying.Keying` owns key-lifecycle IO (enumerating
  and deleting the key pairs it names — only it knows the layout);
- the policy owns entry-level IO (get/put/vacuum/size — it must orchestrate
  keying, hasher and scripts);
- :class:`~redis_func_cache.scripts.Scripts` stays pure declaration (script
  names, ARGV builders) plus per-client script registration.

Like :class:`~redis_func_cache.keying.Keying`, a policy is **completely
stateless**: it holds no namespace, no client and no cache reference. The key
namespace (``prefix`` / ``name``) is passed to every method that needs it, so
built-in preset instances (``lru_policy``, ``rr_policy``, ...) can be shared
freely across caches and processes — there is never a reason to copy one.

Build a custom policy by composing components::

    from dataclasses import replace

    from redis_func_cache.hashing import JsonMd5Hasher
    from redis_func_cache.keying import SingleKeying
    from redis_func_cache.scripts import LruScripts


    class StableJsonMd5Hasher(JsonMd5Hasher):
        __hash_config__ = replace(JsonMd5Hasher.__hash_config__, use_bytecode=False)


    policy = Policy(SingleKeying("my-lru"), StableJsonMd5Hasher(), LruScripts())
    cache = RedisFuncCache("my-cache", policy, factory=factory)

The built-in policies (``lru_policy``, ``rr_policy``, ...) are preset
:class:`Policy` instances — despite living in the package namespace under
snake_case names, they are objects, not classes.

.. versionchanged:: 1.0
    Replaces the mixin-based ``AbstractPolicy`` class hierarchy. Custom policies
    are now built by composition rather than by subclassing mixins. The policy
    no longer stores the key namespace: ``prefix`` / ``name`` are explicit
    arguments, and preset instances are shareable singletons.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from typing import TYPE_CHECKING, Any, cast

from redis.commands.core import AsyncScript, Script
from redis.typing import EncodedT

from ..scripts import Scripts, build_get_args, build_put_args

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, KeyT

from ..hashing import Hasher
from ..keying import Keying

if TYPE_CHECKING:  # pragma: no cover
    from ..typing import HashValueT, KeyNameT, RedisAsyncClientT, RedisClientT, RedisSyncClientT

__all__ = ("Policy",)


class Policy:
    """A caching policy composed of a keying, a hasher and a scripts component.

    .. admonition:: Stateless component, explicit namespace

        A policy holds no per-cache state: the key namespace (``prefix`` /
        ``name``) is an explicit argument of every method that builds or
        enumerates key names, supplied by :class:`RedisFuncCache` at each call.
        Preset policy instances are therefore safe to share across caches.

    .. admonition:: Redis client lifecycle contract

        Every method that talks to Redis takes the client as an explicit
        ``redis_client`` argument — supplied by :class:`RedisFuncCache`, which
        obtains it from the user's ``redis_client`` or ``factory``. Policy code
        must **never** obtain a client itself and must **never** store a client
        on the instance: with a ``factory``, clients are per-operation and must
        not outlive the call. The only cacheable artifacts are
        client-independent ones (script *text*, key names). Registered script
        objects are cached inside :attr:`scripts`, keyed weakly by client, so
        they never outlive the client they were registered against.
    """

    keying: Keying
    """The key-naming component."""
    hasher: Hasher
    """The sub-key hashing component."""
    scripts: Scripts
    """The Lua scripts / Redis-structure component."""

    def __init__(self, keying: Keying, hasher: Hasher, scripts: Scripts) -> None:
        """Compose a policy from its three components.

        The policy is stateless and may be instantiated standalone and shared;
        :class:`RedisFuncCache` passes its key namespace (``prefix`` and
        ``name``) to the policy's methods at every call.

        Args:
            keying: The key-naming component.
            hasher: The sub-key hashing component.
            scripts: The Lua scripts / Redis-structure component.
        """
        self.keying = keying
        self.hasher = hasher
        self.scripts = scripts

    def __repr__(self) -> str:
        keying = type(self.keying).__name__
        hasher = type(self.hasher).__name__
        scripts = type(self.scripts).__name__
        return f"{self.__class__.__name__}({keying}({self.keying.key!r}), {hasher}(), {scripts}())"

    # --- hash dimension ---------------------------------------------------

    def calc_hash(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> HashValueT:
        """Calculate the sub-key hash for the function and its arguments.

        Delegates to :attr:`hasher`.

        Args:
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            The calculated hash value.
        """
        return self.hasher.calc_hash(fn, args, kwds)

    # --- keying dimension -------------------------------------------------

    def calc_key_pair(
        self,
        prefix: str,
        name: str,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Calculate the Redis key pair for caching. Delegates to :attr:`keying`.

        Args:
            prefix: The cache's key prefix.
            name: The cache's name.
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Tuple of two Redis key names (index key, value key).
        """
        return self.keying.calc_key_pair(prefix, name, fn, args, kwds)

    def iterate_key_pairs(
        self, redis_client: RedisSyncClientT, prefix: str, name: str
    ) -> Iterator[tuple[KeyNameT, KeyNameT]]:
        """Iterate over the (index key, value key) pairs owned by this policy.

        The read-only twin of :meth:`purge_all_pairs`: used internally by
        :meth:`vacuum` / :meth:`get_size`, and part of the policy's user
        introspection surface for building custom maintenance or inspection
        tools. Streams lazily — nothing is materialized. See
        :meth:`Keying.iterate_key_pairs <redis_func_cache.keying.Keying.iterate_key_pairs>`.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.

        Returns:
            Iterator of (index key, value key) pairs.
        """
        return self.keying.iterate_key_pairs(redis_client, prefix, name)

    def aiterate_key_pairs(
        self, redis_client: RedisAsyncClientT, prefix: str, name: str
    ) -> AsyncIterator[tuple[KeyNameT, KeyNameT]]:
        """Async version of :meth:`iterate_key_pairs`.

        Not a coroutine: returns the async iterator directly, so callers can
        ``async for`` over it without awaiting first.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.

        Returns:
            Async iterator of (index key, value key) pairs.
        """
        return self.keying.aiterate_key_pairs(redis_client, prefix, name)

    def purge_all_pairs(self, redis_client: RedisSyncClientT, prefix: str, name: str, batch_size: int = 500) -> int:
        """Purge the cache synchronously. Delegates to :attr:`keying`.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.
            batch_size: The number of keys per deletion command.

        Returns:
            Number of keys deleted.
        """
        return self.keying.purge(redis_client, prefix, name, batch_size)

    async def apurge_all_pairs(
        self, redis_client: RedisAsyncClientT, prefix: str, name: str, batch_size: int = 500
    ) -> int:
        """Async version of :meth:`purge_all_pairs`.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.
            batch_size: The number of keys per deletion command.

        Returns:
            Number of keys deleted.
        """
        return await self.keying.apurge(redis_client, prefix, name, batch_size)

    def purge_one_pair(self, redis_client: RedisSyncClientT, index_key: KeyNameT, value_key: KeyNameT) -> int:
        """Delete one (index, value) key pair outright.

        The granularity counterpart of :meth:`vacuum_one_pair`: where vacuum
        removes the expired *members* of a pair, this removes the pair itself.
        Takes raw key names — typically obtained from :meth:`iterate_key_pairs`
        or :meth:`calc_key_pair` — so the semantics are unambiguous regardless
        of the keying variant (under ``MultipleKeying`` a function's entries
        span several pairs; the caller knows exactly which one is deleted).

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            index_key: The index key (ZSET, or SET for the RR family).
            value_key: The value key (HASH).

        Returns:
            Number of keys actually deleted (0, 1 or 2).

        .. versionadded:: 1.0
        """
        return redis_client.unlink(index_key, value_key)

    async def apurge_one_pair(self, redis_client: RedisAsyncClientT, index_key: KeyNameT, value_key: KeyNameT) -> int:
        """Async version of :meth:`purge_one_pair`.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            index_key: The index key (ZSET, or SET for the RR family).
            value_key: The value key (HASH).

        Returns:
            Number of keys actually deleted (0, 1 or 2).

        .. versionadded:: 1.0
        """
        return await redis_client.unlink(index_key, value_key)

    def _fetch_index_size(self, redis_client: RedisSyncClientT, index_key: KeyNameT) -> int:
        """Cardinality of one index structure — ``ZCARD``, or ``SCARD`` for the RR family."""
        if self.scripts.index_structure == "set":
            return redis_client.scard(index_key)
        return redis_client.zcard(index_key)

    async def _afetch_index_size(self, redis_client: RedisAsyncClientT, index_key: KeyNameT) -> int:
        """Async version of :meth:`_fetch_index_size`."""
        if self.scripts.index_structure == "set":
            return await redis_client.scard(index_key)
        return await redis_client.zcard(index_key)

    def get_size(self, redis_client: RedisSyncClientT, prefix: str, name: str) -> int:
        """Get the number of items in the cache synchronously.

        Reports the sum of the index structure cardinalities (``ZCARD``, or
        ``SCARD`` for the set-based RR family, selected via
        :attr:`Scripts.index_structure <redis_func_cache.scripts.Scripts.index_structure>`),
        which is the same number the eviction
        script enforces ``maxsize`` against. With per-item TTL, expired-but-not-
        yet-vacuumed entries ("ghosts") keep this number elevated; the count of
        live values is the HASH length (``HLEN``) of the second key.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.

        Returns:
            Number of items in the cache.
        """
        return sum(
            self._fetch_index_size(redis_client, index_key)
            for index_key, _ in self.keying.iterate_key_pairs(redis_client, prefix, name)
        )

    async def aget_size(self, redis_client: RedisAsyncClientT, prefix: str, name: str) -> int:
        """Async version of :meth:`get_size`; see it for the size semantics.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.

        Returns:
            Number of items in the cache.
        """
        total = 0
        async for index_key, _ in self.keying.aiterate_key_pairs(redis_client, prefix, name):
            total += await self._afetch_index_size(redis_client, index_key)
        return total

    # --- entry-level IO: script invocation and per-pair maintenance ---------

    def locate(
        self,
        prefix: str,
        name: str,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[tuple[KeyT, KeyT], HashValueT]:
        """Compute the ``(key pair, hash value)`` locating one call in the cache.

        A pure query combining :meth:`calc_key_pair` and :meth:`calc_hash` —
        handy for inspecting which Redis keys and hash field a decorated call
        maps to. :meth:`get` / :meth:`put` (and their async mirrors) use it
        internally.

        Args:
            prefix: The cache's key prefix.
            name: The cache's name.
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Tuple of the ``(index_key, hash_key)`` pair and the hash value.

        .. versionadded:: 1.0
        """
        key_pair = self.calc_key_pair(prefix, name, fn, args, kwds)
        return key_pair, self.calc_hash(fn, args, kwds)

    def get(
        self,
        redis_client: RedisClientT,
        prefix: str,
        name: str,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
        *,
        update_ttl: bool,
        ttl: int,
        options: Mapping[str, Any] | None = None,
        located: tuple[tuple[KeyT, KeyT], HashValueT] | None = None,
    ) -> EncodedT | None:
        """Attempt one cache read: run the get Lua script for this call.

        Registers the get script against the given client (cached per client)
        and invokes it with the ARGV layout built by
        :func:`~redis_func_cache.scripts.build_get_args`.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.
            update_ttl: Whether to refresh the TTL of the cache structures on this access.
            ttl: Time-to-live of the cache in seconds.
            options: Reserved for future use.
            located: Pre-computed ``(key pair, hash value)`` from
                :meth:`locate`. When omitted it is computed here; callers that
                already located the call (e.g. to build a handler context)
                pass it in so the identity is computed once per call.

        Returns:
            The serialized hit value, or :data:`None` on a miss.
        """
        if located is None:
            located = self.locate(prefix, name, fn, args, kwds)
        keys, hash_value = located
        get_script, _ = self.scripts.register_scripts(redis_client)
        return cast(EncodedT | None, get_script(keys=keys, args=build_get_args(update_ttl, ttl, hash_value, options)))

    async def aget(
        self,
        redis_client: RedisClientT,
        prefix: str,
        name: str,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
        *,
        update_ttl: bool,
        ttl: int,
        options: Mapping[str, Any] | None = None,
        located: tuple[tuple[KeyT, KeyT], HashValueT] | None = None,
    ) -> EncodedT | None:
        """Async version of :meth:`get`; see it for the semantics of ``located``."""
        if located is None:
            located = self.locate(prefix, name, fn, args, kwds)
        keys, hash_value = located
        get_script, _ = self.scripts.register_scripts(redis_client)
        return cast(
            EncodedT | None, await get_script(keys=keys, args=build_get_args(update_ttl, ttl, hash_value, options))
        )

    def put(
        self,
        redis_client: RedisClientT,
        prefix: str,
        name: str,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
        *,
        value: EncodableT,
        maxsize: int,
        update_ttl: bool,
        ttl: int,
        field_ttl: int = 0,
        options: Mapping[str, Any] | None = None,
        located: tuple[tuple[KeyT, KeyT], HashValueT] | None = None,
    ) -> None:
        """Store one call result: run the put Lua script for this call.

        On reaching ``maxsize`` the script evicts items according to the policy
        before inserting. The ARGV layout is built by
        :func:`~redis_func_cache.scripts.build_put_args`; extra arguments from
        :meth:`Scripts.calc_ext_args` start at ARGV[7] and the reserved options
        JSON goes last — the Lua scripts rely on that fixed layout.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.
            value: The serialized value to store.
            maxsize: The maximum size of the cache.
            update_ttl: Whether to refresh the TTL of the cache structures on this write.
            ttl: Time-to-live of the cache in seconds.
            field_ttl: Time-to-live of the hash field.
            options: Reserved for future use.
            located: Pre-computed ``(key pair, hash value)`` from
                :meth:`locate`. When omitted it is computed here; callers that
                already located the call (e.g. to build a handler context)
                pass it in so the identity is computed once per call. Note
                ``fn`` / ``args`` / ``kwds`` are still used for
                :meth:`Scripts.calc_ext_args`.
        """
        if located is None:
            located = self.locate(prefix, name, fn, args, kwds)
        keys, hash_value = located
        ext_args = self.scripts.calc_ext_args(fn, args, kwds)
        _, put_script = self.scripts.register_scripts(redis_client)
        put_script(
            keys=keys,
            args=build_put_args(maxsize, update_ttl, ttl, hash_value, value, field_ttl, ext_args, options),
        )

    async def aput(
        self,
        redis_client: RedisClientT,
        prefix: str,
        name: str,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
        *,
        value: EncodableT,
        maxsize: int,
        update_ttl: bool,
        ttl: int,
        field_ttl: int = 0,
        options: Mapping[str, Any] | None = None,
        located: tuple[tuple[KeyT, KeyT], HashValueT] | None = None,
    ) -> None:
        """Async version of :meth:`put`; see it for the semantics of ``located``."""
        if located is None:
            located = self.locate(prefix, name, fn, args, kwds)
        keys, hash_value = located
        ext_args = self.scripts.calc_ext_args(fn, args, kwds)
        _, put_script = self.scripts.register_scripts(redis_client)
        await put_script(
            keys=keys,
            args=build_put_args(maxsize, update_ttl, ttl, hash_value, value, field_ttl, ext_args, options),
        )

    # --- maintenance --------------------------------------------------------

    def vacuum_one_pair(
        self, redis_client: RedisSyncClientT, index_key: KeyNameT, value_key: KeyNameT, batch_size: int
    ) -> int:
        """Vacuum one (index, value) key pair; see :meth:`vacuum_all_pairs` for the semantics."""
        script = cast(Script, self.scripts.register_vacuum_script(redis_client))
        removed = 0
        cursor: int | str | bytes = 0
        while True:
            cursor, removed_in_chunk = script(keys=(index_key, value_key), args=(cursor, batch_size))
            removed += removed_in_chunk
            if cursor in (0, b"0", "0"):
                return removed

    def vacuum_all_pairs(self, redis_client: RedisSyncClientT, prefix: str, name: str, batch_size: int = 500) -> int:
        """Remove index members whose hash fields have expired ("ghost" entries).

        Ghost entries appear when a per-field TTL expires a hash field while the
        matching index member survives. Every key pair of this policy is scanned
        in batches; each script invocation performs one scan step plus the probe
        and the removal atomically, and the loop runs until the cursor returns
        to zero.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.
            batch_size: The number of members to fetch per scan step.

        Returns:
            The number of ghost entries removed.
        """
        return sum(
            self.vacuum_one_pair(redis_client, index_key, value_key, batch_size)
            for index_key, value_key in self.iterate_key_pairs(redis_client, prefix, name)
        )

    async def avacuum_one_pair(
        self, redis_client: RedisAsyncClientT, index_key: KeyNameT, value_key: KeyNameT, batch_size: int
    ) -> int:
        """Async version of :meth:`vacuum_one_pair`."""
        script = cast(AsyncScript, self.scripts.register_vacuum_script(redis_client))
        removed = 0
        cursor: int | str | bytes = 0
        while True:
            cursor, removed_in_chunk = await script(keys=(index_key, value_key), args=(cursor, batch_size))
            removed += removed_in_chunk
            if cursor in (0, b"0", "0"):
                return removed

    async def avacuum_all_pairs(
        self, redis_client: RedisAsyncClientT, prefix: str, name: str, batch_size: int = 500
    ) -> int:
        """Async version of :meth:`vacuum_all_pairs`.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            prefix: The cache's key prefix.
            name: The cache's name.
            batch_size: The number of members to fetch per scan step.

        Returns:
            The number of ghost entries removed.
        """
        removed = 0
        async for index_key, value_key in self.aiterate_key_pairs(redis_client, prefix, name):
            removed += await self.avacuum_one_pair(redis_client, index_key, value_key, batch_size)
        return removed
