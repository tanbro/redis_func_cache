from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from redis.commands.core import AsyncScript, Script

from ..typing import is_redis_async_client, is_redis_sync_client
from ..utils import read_lua_file

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, KeyT, ScriptTextT

    from ..typing import RedisClientT


__all__ = ("AbstractPolicy",)


class AbstractPolicy(ABC):
    """
    Abstract base class for cache eviction policies used by :class:`RedisFuncCache`.

    .. inheritance-diagram:: AbstractPolicy
        :parts: 1

    Subclasses **MUST** implement:
      - :meth:`calc_keys`
      - :meth:`calc_hash`

    Optionally, subclasses may define:
      - __key__: A string component used in Redis key naming.
      - __scripts__: A tuple of two Lua script filenames (get, put).

    The use of :attr:`__key__` or :attr:`__scripts__` depends on the implementation of :meth:`calc_keys` and :meth:`calc_hash`.

    .. admonition:: Redis client lifecycle contract

        Every method that talks to Redis takes the client as an explicit
        ``redis_client`` argument — supplied by :class:`RedisFuncCache`, which
        obtains it from the user's ``redis_client`` or ``factory``. Policy code
        must **never** obtain a client itself and must **never** store a client
        on the instance: with a ``factory``, clients are per-operation and must
        not outlive the call. The only cacheable artifacts are
        client-independent ones (script *text*, key names, the bound
        :attr:`_prefix` / :attr:`_name` values).
    """

    __key__: str
    __scripts__: tuple[str, str]

    def __init__(self) -> None:
        """Initialize the policy with no bound cache identity yet.

        Note:
            The policy may be instantiated standalone. :class:`RedisFuncCache`
            binds its key namespace (``prefix`` and ``name``) onto the policy via
            :meth:`_bind` during cache construction — a plain value copy, not an
            object reference, so no reference cycle exists between the two.
        """
        self._prefix: str | None = None
        self._name: str | None = None

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

    @abstractmethod
    def calc_keys(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """
        Calculate the Redis key pair for caching.

        Args:
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Tuple of two Redis key names (e.g., for set and hash).
        """
        raise NotImplementedError()  # pragma: no cover

    @abstractmethod
    def calc_hash(
        self,
        fn: Callable | None = None,
        args: tuple[Any, ...] | None = None,
        kwds: dict[str, Any] | None = None,
    ) -> KeyT:
        """
        Calculate a unique hash for the function and its arguments.

        Args:
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            The calculated hash value.
        """
        raise NotImplementedError()  # pragma: no cover

    def calc_ext_args(
        self, fn: Callable | None = None, args: Sequence | None = None, kwds: Mapping[str, Any] | None = None
    ) -> Iterable[EncodableT] | None:
        """
        Optionally calculate extra arguments to pass to the Lua script.

        Args:
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Iterable of extra encodable arguments, or None.
        """
        return None

    def read_lua_scripts(self) -> tuple[ScriptTextT, ScriptTextT]:
        """
        Read and clean the Lua scripts from package resources.

        Returns:
            Tuple of cleaned Lua script texts (get, put).
        """
        return (read_lua_file(self.__scripts__[0]), read_lua_file(self.__scripts__[1]))

    def read_vacuum_script(self) -> str:
        """
        Read and clean the vacuum Lua script from package resources.

        Returns:
            The cleaned vacuum Lua script text.
        """
        return read_lua_file("vacuum.lua")

    def lua_scripts(self, redis_client: RedisClientT) -> tuple[Script, Script] | tuple[AsyncScript, AsyncScript]:
        """
        Register the get/put Lua scripts against the given client and return them.

        Registration is a local operation (the script SHA is computed, no server
        round trip), so it is repeated per call against the *current* client: with
        a ``factory``, each call may receive a different client instance, and the
        returned Script objects must follow it.

        Args:
            redis_client: The redis client to register the scripts with.

        Returns:
            Tuple of registered Script or AsyncScript objects (get, put).

        .. versionchanged:: TODO
            Was a cached property taking no arguments. Caching bound the returned
            Script objects to whichever client was current on first access, so
            with a ``factory`` all script calls were funneled through a stale
            client. It is now a method registering against the client passed in;
            subclasses that overrode the property must adapt.
        """
        script_texts = self.read_lua_scripts()
        # Which side of the union applies follows the client; callers narrow via
        # the existing sync/async script checks.
        return cast(
            "tuple[Script, Script] | tuple[AsyncScript, AsyncScript]",
            (
                redis_client.register_script(script_texts[0]),
                redis_client.register_script(script_texts[1]),
            ),
        )

    def vacuum_script(self, redis_client: RedisClientT) -> Script | AsyncScript:
        """
        Register the vacuum Lua script against the given client and return it.

        Mirrors :meth:`lua_scripts`: registration is local and repeated per call
        against the *current* client.

        Args:
            redis_client: The redis client to register the script with.

        Returns:
            The registered vacuum Script or AsyncScript object.

        .. versionchanged:: TODO
            Was a cached property taking no arguments, for the same reason as
            :meth:`lua_scripts`; it now registers against the client passed in.
        """
        return redis_client.register_script(self.read_vacuum_script())

    @abstractmethod
    def calc_key_pairs(self, redis_client: RedisClientT) -> list[tuple[KeyT, KeyT]]:
        """
        Return the (sorted-set key, hash-map key) pairs to vacuum.

        Provided by the single/multiple base classes: single policies return the
        static key pair, multiple policies enumerate their pairs by pattern.

        Args:
            redis_client: A synchronous redis client, already guarded by the caller.

        Returns:
            List of (sorted-set key, hash-map key) pairs.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover

    @abstractmethod
    async def acalc_key_pairs(self, redis_client: RedisClientT) -> list[tuple[KeyT, KeyT]]:
        """
        Async version of :meth:`calc_key_pairs`.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover

    def vacuum(self, redis_client: RedisClientT, batch_size: int = 500) -> int:
        """
        Remove ZSET members whose hash fields have expired ("ghost" entries).

        Ghost entries appear when a per-field TTL expires a hash field while the
        matching sorted-set member survives. This method scans the sorted set(s) in
        batches and removes members whose hash fields are gone.

        Each script invocation performs one ZSCAN step plus the probe and the
        removal atomically, and returns the next cursor; this method loops until
        the cursor returns to zero.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            batch_size: The number of members to fetch per scan step.

        Returns:
            The number of ghost entries removed.

        Raises:
            RuntimeError: If the given redis client is asynchronous.

        .. versionadded:: TODO
        """
        if not is_redis_sync_client(redis_client):
            raise RuntimeError("Can not perform a synchronous operation with an asynchronous redis client")
        script = cast(Script, self.vacuum_script(redis_client))
        removed = 0
        for zset_key, hmap_key in self.calc_key_pairs(redis_client):
            cursor: int | str | bytes = 0
            while True:
                cursor, removed_in_chunk = script(keys=(zset_key, hmap_key), args=(cursor, batch_size))
                removed += removed_in_chunk
                if cursor in (0, b"0", "0"):
                    break
        return removed

    async def avacuum(self, redis_client: RedisClientT, batch_size: int = 500) -> int:
        """
        Async version of :meth:`vacuum`.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            batch_size: The number of members to fetch per scan step.

        Returns:
            The number of ghost entries removed.

        Raises:
            RuntimeError: If the given redis client is synchronous.

        .. versionadded:: TODO
        """
        if not is_redis_async_client(redis_client):
            raise RuntimeError("Can not perform an asynchronous operation with a synchronous redis client")
        script = cast(AsyncScript, self.vacuum_script(redis_client))
        removed = 0
        for zset_key, hmap_key in await self.acalc_key_pairs(redis_client):
            cursor: int | str | bytes = 0
            while True:
                cursor, removed_in_chunk = await script(keys=(zset_key, hmap_key), args=(cursor, batch_size))
                removed += removed_in_chunk
                if cursor in (0, b"0", "0"):
                    break
        return removed

    @abstractmethod
    def purge(self, redis_client: RedisClientT, batch_size: int = 500) -> int:
        """
        Purge the cache.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.
            batch_size: The number of keys per deletion command.

        Returns:
            Number of items removed (if implemented).

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover

    @abstractmethod
    async def apurge(self, redis_client: RedisClientT, batch_size: int = 500) -> int:
        """
        Asynchronously purge the cache.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.
            batch_size: The number of keys per deletion command.

        Returns:
            Number of items removed (if implemented).

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover

    @abstractmethod
    def get_size(self, redis_client: RedisClientT) -> int:
        """
        Get the number of items in the cache.

        Args:
            redis_client: A synchronous redis client obtained from the bound cache.

        Returns:
            The cache size.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover

    @abstractmethod
    async def aget_size(self, redis_client: RedisClientT) -> int:
        """
        Asynchronously get the number of items in the cache.

        Args:
            redis_client: An asynchronous redis client obtained from the bound cache.

        Returns:
            The cache size.

        Raises:
            NotImplementedError: If not implemented by subclass.
        """
        raise NotImplementedError()  # pragma: no cover
