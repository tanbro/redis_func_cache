"""Scripts: the *declarations* dimension of a policy.

A :class:`Scripts` object declares everything needed to *state* what a policy
runs against Redis — it does not invoke anything:

- which Lua script files implement the get/put/vacuum operations,
- which Redis structure the index is (sorted set vs set),
- any extra ARGV entries the scripts expect (e.g. the MRU flag on ARGV[7]).

Its only actions are :meth:`Scripts.register_scripts` and
:meth:`Scripts.register_vacuum_script`, which bind the declared files to a
client. All invocation lives on
:class:`~redis_func_cache.policies.Policy`, the single entry point to the
Redis side; the ARGV layout shared by the scripts is encoded by the
module-level :func:`build_get_args` / :func:`build_put_args` helpers.

It is one of the three orthogonal components composed into a
:class:`~redis_func_cache.policies.Policy`:

- :class:`~redis_func_cache.keying.Keying` — how Redis keys are named
- :class:`~redis_func_cache.hashing.Hasher` — how each call is hashed to a sub-key
- :class:`Scripts` — which Lua scripts run and what they expect

.. versionchanged:: 1.0
    Replaces the ``mixins.scripts`` mixin classes; invocation moved to Policy.
"""

from __future__ import annotations

import math
from abc import ABC
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast
from weakref import WeakKeyDictionary

from redis.commands.core import AsyncScript, Script
from redis.typing import ScriptTextT

from .serializers import json_encode
from .typing import RedisClientT
from .utils import read_lua_file

if TYPE_CHECKING:  # pragma: no cover
    from typing import Literal

    from redis.typing import EncodableT

__all__ = (
    "FifoScripts",
    "FifoTScripts",
    "GdsfScripts",
    "HyperbolicScripts",
    "LfuScripts",
    "LruScripts",
    "LruTScripts",
    "MruScripts",
    "RandomAdmissionScripts",
    "RrScripts",
    "Scripts",
    "build_get_args",
    "build_put_args",
)


def build_get_args(
    update_ttl: bool,
    ttl: int,
    hash_value: EncodableT,
    options: Mapping[str, Any] | None = None,
) -> list[EncodableT]:
    """Assemble the ARGV list of the get Lua scripts.

    Layout: ``ARGV[1]=update_ttl, ARGV[2]=ttl, ARGV[3]=hash_value,
    ARGV[4]=options JSON``. The options JSON is serialized here; pass
    :data:`None` for the reserved slot.

    Args:
        update_ttl: Whether to refresh the TTL of the cache structures.
        ttl: Time-to-live of the cache in seconds.
        hash_value: The hash of this call (index member / hash field).
        options: Reserved options mapping, or None.

    Returns:
        The ARGV list expected by the get scripts.
    """
    encoded_options = json_encode(options) if options is not None else b"{}"
    return [int(update_ttl), ttl, hash_value, encoded_options]


def build_put_args(
    maxsize: int,
    update_ttl: bool,
    ttl: int,
    hash_value: EncodableT,
    value: EncodableT,
    field_ttl: int,
    ext_args: Iterable[EncodableT] | None = None,
    options: Mapping[str, Any] | None = None,
) -> list[EncodableT]:
    """Assemble the ARGV list of the put Lua scripts.

    The core arguments occupy ARGV[1..6]; any extra arguments (e.g. the MRU
    flag) start at ARGV[7]; the reserved options JSON always goes last —
    the Lua scripts rely on that fixed layout.

    Args:
        maxsize: The maximum size of the cache.
        update_ttl: Whether to refresh the TTL of the cache structures.
        ttl: Time-to-live of the cache in seconds.
        hash_value: The hash of this call (index member / hash field).
        value: The serialized value to store.
        field_ttl: Time-to-live of the hash field.
        ext_args: Extra arguments from :meth:`Scripts.calc_ext_args`.
        options: Reserved options mapping, or None.

    Returns:
        The ARGV list expected by the put scripts.
    """
    encoded_options = json_encode(options) if options is not None else b"{}"
    return [maxsize, int(update_ttl), ttl, hash_value, value, field_ttl, *(ext_args or ()), encoded_options]


class Scripts(ABC):
    """Declare the Lua scripts and Redis-structure facts of a policy.

    Subclasses set :attr:`get_script` / :attr:`put_script` /
    :attr:`vacuum_script` / :attr:`index_structure` and may override
    :meth:`calc_ext_args` (extra ARGV entries). Invoking the scripts is the
    policy's job, not this class's.
    """

    get_script: str
    """File name of the Lua script implementing the cache read."""
    put_script: str
    """File name of the Lua script implementing the cache write."""
    vacuum_script: str = "vacuum.lua"
    """File name of the Lua script implementing vacuum."""
    index_structure: Literal["zset", "set"] = "zset"
    """The Redis structure of the index (``KEYS[1]`` of the scripts).

    ``"zset"`` (default) means the sorted-set based policies, ``"set"`` the
    RR family. Consumed by :meth:`Policy.get_size` to dispatch between
    ``ZCARD`` and ``SCARD`` when counting entries.
    """

    def __init__(self) -> None:
        self._registered: WeakKeyDictionary[RedisClientT, tuple[Script, Script] | tuple[AsyncScript, AsyncScript]] = (
            WeakKeyDictionary()
        )
        self._registered_vacuum: WeakKeyDictionary[RedisClientT, Script | AsyncScript] = WeakKeyDictionary()

    def calc_ext_args(
        self,
        fn: Callable | None = None,
        args: Sequence | None = None,
        kwds: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> Iterable[EncodableT] | None:
        """Extra ARGV entries the scripts expect, beyond the core put arguments.

        The core arguments occupy ARGV[1..6]; the first value returned here must
        land on ARGV[7] (e.g. the MRU flag); the reserved options JSON goes last.

        Args:
            fn: The function being cached.
            args: Positional arguments.
            kwds: Keyword arguments.
            options: Decorator-local keyword arguments from ``cache(...)``
                (may be None); policies that need a per-function declaration
                (e.g. GDSF's ``cost``) read it here.

        Returns:
            Iterable of extra encodable arguments, or None.
        """
        return None

    def read_lua_scripts(self) -> tuple[ScriptTextT, ScriptTextT]:
        """Read and clean the get/put Lua scripts from package resources."""
        return (read_lua_file(self.get_script), read_lua_file(self.put_script))

    def read_vacuum_script(self) -> str:
        """Read and clean the vacuum Lua script from package resources."""
        return read_lua_file(self.vacuum_script)

    def register_scripts(self, redis_client: RedisClientT) -> tuple[Script, Script] | tuple[AsyncScript, AsyncScript]:
        """Register the get/put Lua scripts against the given client.

        Registration is a local operation (the script SHA is computed, no
        server round trip). Results are cached per client instance: with a
        ``factory``, each call may receive a different client, and the returned
        Script objects must follow it. A ``TypeError`` from the cache means the
        client is unhashable or cannot be weak-referenced and is raised as-is.

        Args:
            redis_client: The redis client to register the scripts with.

        Returns:
            Tuple of registered Script or AsyncScript objects (get, put).
        """
        registered = self._registered.get(redis_client)
        if registered is None:
            script_texts = self.read_lua_scripts()
            registered = cast(
                tuple[Script, Script] | tuple[AsyncScript, AsyncScript],
                (redis_client.register_script(script_texts[0]), redis_client.register_script(script_texts[1])),
            )
            self._registered[redis_client] = registered
        return registered

    def register_vacuum_script(self, redis_client: RedisClientT) -> Script | AsyncScript:
        """Register the vacuum Lua script against the given client.

        Mirrors :meth:`register_scripts`, including the per-client cache.

        Args:
            redis_client: The redis client to register the script with.

        Returns:
            The registered vacuum Script or AsyncScript object.
        """
        registered = self._registered_vacuum.get(redis_client)
        if registered is None:
            registered = redis_client.register_script(self.read_vacuum_script())
            self._registered_vacuum[redis_client] = registered
        return registered


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


class HyperbolicScripts(Scripts):
    """Scripts for the Hyperbolic policies (sorted set index, LFU-with-aging scores).

    The score is the Hyperbolic priority ``log(freq + 1) / (age + 1) ^ 0.25``,
    recomputed on every access from a per-entry metadata field
    (``<hash>:m`` in the value hash) that stores the access frequency and the
    insertion time. See ``lua/hyperbolic_put.lua`` for the full contract.
    """

    get_script = "hyperbolic_get.lua"
    put_script = "hyperbolic_put.lua"


class GdsfScripts(Scripts):
    """Scripts for the GDSF policies (sorted set index, cost-benefit scores).

    The score is the Greedy-Dual-Size priority ``freq * cost / size``
    (Cherkasova 1998), where ``size`` is the serialized byte length of the
    stored value (computed in Lua from ARGV[5]) and ``cost`` is the per-function
    miss cost the user declares as the ``cost`` decorator kwarg. ``cost`` travels
    as an extra argument (ARGV[7]); a per-entry metadata field (``<hash>:m``)
    stores ``"<freq> <cost>"`` so hits can re-score. See ``lua/gdsf_put.lua``.
    """

    get_script = "gdsf_get.lua"
    put_script = "gdsf_put.lua"

    #: Default miss cost when the ``cost`` decorator kwarg is absent.
    DEFAULT_COST = 1.0

    def calc_ext_args(
        self,
        fn: Callable | None = None,
        args: Sequence | None = None,
        kwds: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> tuple[float]:
        """Pass the per-function miss ``cost`` (ARGV[7]).

        Reads the ``cost`` decorator kwarg (default 1.0). The value is coerced
        with ``float()`` — whatever that raises for a non-numeric value is
        propagated as-is; a non-positive or NaN result raises ``ValueError``.
        No fallback, per the GDSF design decision (a zero cost would make every
        score zero and eviction degenerate).
        """
        raw = None if options is None else options.get("cost")
        cost = self.DEFAULT_COST if raw is None else float(raw)
        if math.isnan(cost) or cost <= 0:
            raise ValueError(f"cost must be a positive number (not NaN), got {cost!r}")
        return (cost,)


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
        self,
        fn: Callable | None = None,
        args: Sequence | None = None,
        kwds: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
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


class RandomAdmissionScripts(Scripts):
    """Put-side random admission composed over any base policy's scripts.

    The wrapped base's put script is prefixed, at load time, with an admission
    prologue: entries already present in the index always pass through (an
    update must never be dropped), while a new insertion is rejected with
    probability ``p`` (the script returns 0 without writing). This is the
    fixed-probability admission rule of the ``lru_tr`` family — the cheap
    anti-scan-pollution baseline of the TinyLFU admission principle.

    Notes:

    - The rejection uses Lua's ``math.random``, seeded per script execution
      from Redis 7.0 on; random admission therefore requires **Redis >= 7.0**
      (on older servers the sequence would be deterministic across runs).
    - ``get_script`` / ``put_script`` / ``index_structure`` mirror the base;
      the composed put script is not a package resource (``put_script`` still
      names the base file whose text the prologue prefixes).
    - ``calc_ext_args`` is delegated to the base, so any base policy's extra
      ARGV contract (e.g. MRU's flag) is preserved.
    """

    def __init__(self, base: Scripts, p: float = 0.5) -> None:
        """Compose random admission over a base policy's scripts.

        Args:
            base: The base policy's scripts (any :class:`Scripts` instance).
            p: Probability of rejecting a new insertion, within ``[0, 1]``.
                ``0`` admits everything, ``1`` rejects every new insertion
                (updates still pass). Non-numeric values propagate whatever
                ``float()`` raises; a value outside the range (or NaN) raises
                ``ValueError``.
        """
        super().__init__()
        probability = float(p)
        if math.isnan(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError(f"admission probability must be within [0, 1], got {p!r}")
        self.base = base
        self.p = probability
        self.get_script = base.get_script
        self.put_script = base.put_script
        self.index_structure = base.index_structure

    def calc_ext_args(
        self,
        fn: Callable | None = None,
        args: Sequence | None = None,
        kwds: Mapping[str, Any] | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> Iterable[EncodableT] | None:
        """Delegate to the base scripts' extra ARGV entries."""
        return self.base.calc_ext_args(fn, args, kwds, options)

    def read_lua_scripts(self) -> tuple[ScriptTextT, ScriptTextT]:
        """Read the base scripts, prefixing the put script with the prologue."""
        get_text, put_text = self.base.read_lua_scripts()
        return (get_text, cast(ScriptTextT, self._admission_prologue() + cast(str, put_text)))

    def _admission_prologue(self) -> str:
        """Lua prologue: reject new insertions with probability ``p``."""
        exists_command = "SISMEMBER" if self.index_structure == "set" else "ZSCORE"
        return (
            "-- >>> random admission prologue (composed by RandomAdmissionScripts).\n"
            "-- Updates pass unconditionally; new insertions are rejected with\n"
            f"-- probability {self.p!r} (requires Redis >= 7.0 for a random seed).\n"
            f"local __ra_exists = redis.call('{exists_command}', KEYS[1], ARGV[4])\n"
            "if not __ra_exists then\n"
            f"    if math.random() < {self.p!r} then\n"
            "        return 0\n"
            "    end\n"
            "end\n"
            "-- <<< end random admission prologue\n"
        )
