"""Scripts: the *Redis operations* dimension of a policy.

A :class:`Scripts` object owns everything a policy does against Redis that is
not key naming or hashing:

- which Lua script files implement the get/put operations,
- which Redis structure the index is (sorted set vs set) — a fact
  :meth:`Policy.get_size <redis_func_cache.policies.Policy.get_size>`
  dispatches on when counting,
- any extra ARGV entries the scripts expect (e.g. the MRU flag on ARGV[7]),
- registering the scripts against a client.

It is one of the three orthogonal components composed into a
:class:`~redis_func_cache.policies.Policy`:

- :class:`~redis_func_cache.keying.Keying` — how Redis keys are named
- :class:`~redis_func_cache.hashing.Hasher` — how each call is hashed to a sub-key
- :class:`Scripts` — which Lua scripts run and how they talk to Redis

.. versionchanged:: 1.0
    Replaces the ``mixins.scripts`` mixin classes.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

from redis.commands.core import AsyncScript, Script

from .typing import RedisClientT
from .utils import read_lua_file

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import EncodableT, ScriptTextT

__all__ = (
    "FifoScripts",
    "FifoTScripts",
    "LfuScripts",
    "LruScripts",
    "LruTScripts",
    "MruScripts",
    "RrScripts",
    "Scripts",
)


class Scripts(ABC):
    """Own the Lua scripts and Redis-structure facts of a policy.

    Subclasses set :attr:`get_script` / :attr:`put_script` /
    :attr:`index_structure` and may override :meth:`calc_ext_args`
    (extra ARGV entries).
    """

    get_script: str
    """File name of the Lua script implementing the cache read."""
    put_script: str
    """File name of the Lua script implementing the cache write."""
    index_structure: Literal["zset", "set"] = "zset"
    """The Redis structure of the index (``KEYS[1]`` of the scripts).

    ``"zset"`` (default) for the sorted-set based policies, ``"set"`` for the
    RR family. :meth:`Policy.get_size
    <redis_func_cache.policies.Policy.get_size>` uses this to pick
    ``ZCARD`` or ``SCARD`` when counting.
    """

    def calc_ext_args(
        self, fn: Callable | None = None, args: Sequence | None = None, kwds: Mapping[str, Any] | None = None
    ) -> Iterable[EncodableT] | None:
        """Extra ARGV entries the scripts expect, beyond the core put arguments.

        The core arguments occupy ARGV[1..6]; the first value returned here must
        land on ARGV[7] (e.g. the MRU flag); the reserved options JSON goes last.

        Args:
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.

        Returns:
            Iterable of extra encodable arguments, or None.
        """
        return None

    def read_lua_scripts(self) -> tuple[ScriptTextT, ScriptTextT]:
        """Read and clean the get/put Lua scripts from package resources."""
        return (read_lua_file(self.get_script), read_lua_file(self.put_script))

    def read_vacuum_script(self) -> str:
        """Read and clean the vacuum Lua script from package resources."""
        return read_lua_file("vacuum.lua")

    def lua_scripts(self, redis_client: RedisClientT) -> tuple[Script, Script] | tuple[AsyncScript, AsyncScript]:
        """Register the get/put Lua scripts against the given client and return them.

        Registration is a local operation (the script SHA is computed, no server
        round trip), so it is repeated per call against the *current* client: with
        a ``factory``, each call may receive a different client instance, and the
        returned Script objects must follow it.

        Args:
            redis_client: The redis client to register the scripts with.

        Returns:
            Tuple of registered Script or AsyncScript objects (get, put).
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
        """Register the vacuum Lua script against the given client and return it.

        Mirrors :meth:`lua_scripts`: registration is local and repeated per call
        against the *current* client.

        Args:
            redis_client: The redis client to register the script with.

        Returns:
            The registered vacuum Script or AsyncScript object.
        """
        return redis_client.register_script(self.read_vacuum_script())


class FifoScripts(Scripts):
    """Scripts for the FIFO policies (sorted set index, insertion-order scores)."""

    get_script = "fifo_get.lua"
    put_script = "fifo_put.lua"


class FifoTScripts(Scripts):
    """Scripts for the FIFO-T policies (sorted set index, timestamp scores)."""

    get_script = "fifo_get.lua"
    put_script = "fifo_t_put.lua"


class LfuScripts(Scripts):
    """Scripts for the LFU policies (sorted set index, frequency scores)."""

    get_script = "lfu_get.lua"
    put_script = "lfu_put.lua"


class LruScripts(Scripts):
    """Scripts for the LRU policies (sorted set index, recency scores)."""

    get_script = "lru_get.lua"
    put_script = "lru_put.lua"


class LruTScripts(Scripts):
    """Scripts for the LRU-T policies (sorted set index, timestamp scores)."""

    get_script = "lru_t_get.lua"
    put_script = "lru_t_put.lua"


class MruScripts(Scripts):
    """Scripts for the MRU policies.

    Uses the LRU script pair with the ``mru`` flag passed as an extra argument,
    which must land on ARGV[7].
    """

    get_script = "lru_get.lua"
    put_script = "lru_put.lua"

    def calc_ext_args(
        self, fn: Callable | None = None, args: Sequence | None = None, kwds: Mapping[str, Any] | None = None
    ) -> tuple[str]:
        """Pass the MRU eviction-direction flag (ARGV[7])."""
        return ("mru",)


class RrScripts(Scripts):
    """Scripts for the RR policies.

    The RR family indexes cache entries in a Redis SET instead of a sorted set.
    """

    get_script = "rr_get.lua"
    put_script = "rr_put.lua"
    index_structure = "set"
