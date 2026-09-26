"""Policy: the composition of keying, hashing and scripts dimensions.

A :class:`Policy` is the object a :class:`~redis_func_cache.RedisFuncCache` takes;
it composes the three orthogonal dimensions instead of weaving them through a
multiple-inheritance hierarchy:

- :class:`~redis_func_cache.keying.Keying` — how Redis keys are named
- :class:`~redis_func_cache.hashing.Hasher` — how each call is hashed to a sub-key
- :class:`~redis_func_cache.scripts.Scripts` — which Lua scripts run and how they talk to Redis

Build a custom policy by composing components::

    from dataclasses import replace

    from redis_func_cache.hashing import JsonMd5Hasher
    from redis_func_cache.keying import SingleKeying
    from redis_func_cache.scripts import LruScripts


    class StableJsonMd5Hasher(JsonMd5Hasher):
        __hash_config__ = replace(JsonMd5Hasher.__hash_config__, use_bytecode=False)


    policy = Policy(SingleKeying("my-lru"), StableJsonMd5Hasher(), LruScripts())
    cache = RedisFuncCache("my-cache", policy, factory=factory)

The built-in policies (``LruPolicy``, ``RrPolicy``, ...) are preset
:class:`Policy` instances.

.. versionchanged:: 1.0
    Replaces the mixin-based ``AbstractPolicy`` class hierarchy. Custom policies
    are now built by composition rather than by subclassing mixins.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterator
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import AsyncIterator

from redis.commands.core import AsyncScript, Script

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import ScriptTextT

from ..hashing import Hasher
from ..keying import Keying
from ..scripts import Scripts

if TYPE_CHECKING:  # pragma: no cover
    from ..typing import HashValueT, KeyNameT, RedisAsyncClientT, RedisClientT, RedisSyncClientT

__all__ = ("Policy",)


class Policy:
    """A caching policy composed of a keying, a hasher and a scripts component.

    .. admonition:: Redis client lifecycle contract

        Every method that talks to Redis takes the client as an explicit
        ``redis_client`` argument — supplied by :class:`RedisFuncCache`, which
        obtains it from the user's ``redis_client`` or ``factory``. Policy code
        must **never** obtain a client itself and must **never** store a client
        on the instance: with a ``factory``, clients are per-operation and must
        not outlive the call. The only cacheable artifacts are
        client-independent ones (script *text*, key names, the bound
        ``prefix`` / ``name`` values).
    """

    keying: Keying
    """The key-naming component."""
    hasher: Hasher
    """The sub-key hashing component."""
    scripts: Scripts
    """The Lua scripts / Redis-structure component."""

    def __init__(self, keying: Keying, hasher: Hasher, scripts: Scripts) -> None:
        """Compose a policy from its three components.

        The policy may be instantiated standalone;
        :class:`RedisFuncCache` binds its key namespace (``prefix`` and
        ``name``) onto the policy via :meth:`_bind` during cache construction —
        a plain value copy, not an object reference, so no reference cycle
        exists between the two.

        Args:
            keying: The key-naming component.
            hasher: The sub-key hashing component.
            scripts: The Lua scripts / Redis-structure component.
        """
        self.keying = keying
        self.hasher = hasher
        self.scripts = scripts
        self._prefix: str | None = None
        self._name: str | None = None

    def __repr__(self) -> str:
        keying = type(self.keying).__name__
        hasher = type(self.hasher).__name__
        scripts = type(self.scripts).__name__
        return f"Policy({keying}({self.keying.key!r}), {hasher}(), {scripts}())"

    def _bind(self, prefix: str, name: str) -> None:
        """Bind the cache key namespace (``prefix``, ``name``) onto this policy.

        Called by :class:`RedisFuncCache` at construction time and whenever its
        ``prefix`` or ``name`` properties are reassigned. Values are copied, so
        the policy holds no reference to the cache instance.
        """
        self._prefix = prefix
        self._name = name

    def _require_bound(self) -> tuple[str, str]:
        """Return the bound ``(prefix, name)``, raising if the policy is unbound."""
        if self._prefix is None or self._name is None:
            raise RuntimeError("Policy instance is not bound to a RedisFuncCache")
        return self._prefix, self._name

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

    def calc_ext_args(
        self, fn: Callable | None = None, args: tuple[Any, ...] | None = None, kwds: dict[str, Any] | None = None
    ) -> Any:
        """Extra ARGV entries the scripts expect. Delegates to :attr:`scripts`."""
        return self.scripts.calc_ext_args(fn, args, kwds)

    # --- keying dimension -------------------------------------------------

    def calc_key_pair(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """Calculate the Redis key pair for caching. Delegates to :attr:`keying`.

        Args:
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Tuple of two Redis key names (index key, value key).
        """
        prefix, name = self._require_bound()
        return self.keying.calc_key_pair(prefix, name, fn, args, kwds)

    def iterate_key_pairs(self, redis_client: RedisSyncClientT) -> Iterator[tuple[KeyNameT, KeyNameT]]:
        """Iterate over the (index key, value key) pairs owned by this policy.

        Streams lazily — nothing is materialized. See
        :meth:`Keying.iterate_key_pairs <redis_func_cache.keying.Keying.iterate_key_pairs>`.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.

        Returns:
            Iterator of (index key, value key) pairs.
        """
        prefix, name = self._require_bound()
        return self.keying.iterate_key_pairs(redis_client, prefix, name)

    def aiterate_key_pairs(self, redis_client: RedisAsyncClientT) -> AsyncIterator[tuple[KeyNameT, KeyNameT]]:
        """Async version of :meth:`iterate_key_pairs`.

        Not a coroutine: returns the async iterator directly, so callers can
        ``async for`` over it without awaiting first.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.

        Returns:
            Async iterator of (index key, value key) pairs.
        """
        prefix, name = self._require_bound()
        return self.keying.aiterate_key_pairs(redis_client, prefix, name)

    def purge(self, redis_client: RedisSyncClientT, batch_size: int = 500) -> int:
        """Purge the cache synchronously. Delegates to :attr:`keying`.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            batch_size: The number of keys per deletion command.

        Returns:
            Number of keys deleted.
        """
        prefix, name = self._require_bound()
        return self.keying.purge(redis_client, prefix, name, batch_size)

    async def apurge(self, redis_client: RedisAsyncClientT, batch_size: int = 500) -> int:
        """Async version of :meth:`purge`.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            batch_size: The number of keys per deletion command.

        Returns:
            Number of keys deleted.
        """
        prefix, name = self._require_bound()
        return await self.keying.apurge(redis_client, prefix, name, batch_size)

    def get_size(self, redis_client: RedisSyncClientT) -> int:
        """Get the number of items in the cache synchronously.

        Reports the sum of the index structure cardinalities (``ZCARD``, or
        ``SCARD`` for the set-based RR family, selected via
        :attr:`Scripts.index_structure`), which is the same number the eviction
        script enforces ``maxsize`` against. With per-item TTL, expired-but-not-
        yet-vacuumed entries ("ghosts") keep this number elevated; the count of
        live values is the HASH length (``HLEN``) of the second key.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.

        Returns:
            Number of items in the cache.
        """
        count = redis_client.scard if self.scripts.index_structure == "set" else redis_client.zcard
        return sum(
            count(index_key)  # type: ignore[union-attr, return-value]
            for index_key, _ in self.keying.iterate_key_pairs(redis_client, *self._require_bound())
        )

    async def aget_size(self, redis_client: RedisAsyncClientT) -> int:
        """Async version of :meth:`get_size`; see it for the size semantics.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.

        Returns:
            Number of items in the cache.
        """
        count = redis_client.scard if self.scripts.index_structure == "set" else redis_client.zcard
        total = 0
        async for index_key, _ in self.keying.aiterate_key_pairs(redis_client, *self._require_bound()):
            total += await count(index_key)  # type: ignore[misc, union-attr, return-value]
        return total

    # --- scripts dimension ------------------------------------------------

    def read_lua_scripts(self) -> tuple[ScriptTextT, ScriptTextT]:
        """Read and clean the Lua scripts from package resources. Delegates to :attr:`scripts`."""
        return self.scripts.read_lua_scripts()

    def read_vacuum_script(self) -> str:
        """Read and clean the vacuum Lua script from package resources."""
        return self.scripts.read_vacuum_script()

    def lua_scripts(self, redis_client: RedisClientT) -> tuple[Script, Script] | tuple[AsyncScript, AsyncScript]:
        """Register the get/put Lua scripts against the given client. Delegates to :attr:`scripts`."""
        return self.scripts.lua_scripts(redis_client)

    def vacuum_script(self, redis_client: RedisClientT) -> Script | AsyncScript:
        """Register the vacuum Lua script against the given client. Delegates to :attr:`scripts`."""
        return self.scripts.vacuum_script(redis_client)

    # --- maintenance --------------------------------------------------------

    def vacuum(self, redis_client: RedisSyncClientT, batch_size: int = 500) -> int:
        """Remove index members whose hash fields have expired ("ghost" entries).

        Ghost entries appear when a per-field TTL expires a hash field while the
        matching index member survives. This method scans the index in batches
        and removes members whose hash fields are gone.

        Each script invocation performs one scan step plus the probe and the
        removal atomically, and returns the next cursor; this method loops until
        the cursor returns to zero.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            batch_size: The number of members to fetch per scan step.

        Returns:
            The number of ghost entries removed.

        Raises:
            The client's sync/async nature is enforced statically; passing the
            wrong kind is a type error, not a runtime one.
        """
        script = cast(Script, self.vacuum_script(redis_client))
        removed = 0
        for index_key, value_key in self.iterate_key_pairs(redis_client):
            cursor: int | str | bytes = 0
            while True:
                cursor, removed_in_chunk = script(keys=(index_key, value_key), args=(cursor, batch_size))
                removed += removed_in_chunk
                if cursor in (0, b"0", "0"):
                    break
        return removed

    async def avacuum(self, redis_client: RedisAsyncClientT, batch_size: int = 500) -> int:
        """Async version of :meth:`vacuum`.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            batch_size: The number of members to fetch per scan step.

        Returns:
            The number of ghost entries removed.

        Raises:
            The client's sync/async nature is enforced statically.
        """
        script = cast(AsyncScript, self.vacuum_script(redis_client))
        removed = 0
        async for index_key, value_key in self.aiterate_key_pairs(redis_client):
            cursor: int | str | bytes = 0
            while True:
                cursor, removed_in_chunk = await script(keys=(index_key, value_key), args=(cursor, batch_size))
                removed += removed_in_chunk
                if cursor in (0, b"0", "0"):
                    break
        return removed
