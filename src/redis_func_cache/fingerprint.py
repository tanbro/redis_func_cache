"""Stable fingerprints of callables, shared by hash mixins and multiple policies.

The fingerprint of a callable is the pair of its fullname and (optionally) its
bytecode — the inputs that never change for a given function object. A hash object
seeded with the fingerprint can therefore be computed once and reused: hash digests
are defined over the byte stream, so seeding incrementally is identical to hashing
the concatenation, and any number of readers may call ``digest()``-style accessors
on the seeded object without consuming it. Callers who need to ``update()`` further
data must operate on ``copy()`` and never on the cached object itself.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING

from .utils import calculate_callable_fullname, get_callable_bytecode

if TYPE_CHECKING:  # pragma: no cover
    from .typing import HashProtocol

__all__ = ("MAX_FINGERPRINT_HASH_ENTRIES", "hash_fingerprint")

MAX_FINGERPRINT_HASH_ENTRIES = 1024
"""Upper bound of the fingerprint cache; a safety valve, not a tuned limit.

Entries normally track one decorated function each (dozens to hundreds in real
projects), so the bound is only reached by pathological dynamic-callable usage.
"""


@lru_cache(maxsize=MAX_FINGERPRINT_HASH_ENTRIES)
def hash_fingerprint(algorithm: str, use_bytecode: bool, fn: Callable) -> HashProtocol:
    """Return the hash object seeded with the fingerprint of ``fn``.

    The result is cached per ``(algorithm, use_bytecode, fn)``: the cache key holds
    only the fields the fingerprint consumes, so configurations differing merely in
    digest encoding or in argument serializer share one entry.

    The cached object itself must never be updated — always operate on a copy.

    Args:
        algorithm: Name of the hash algorithm, as accepted by :func:`hashlib.new`.
        use_bytecode: Whether to include the bytecode of ``fn`` in the fingerprint.
        fn: The callable to fingerprint.

    Returns:
        The seeded hash object, suitable for further ``update()`` calls on a
        ``copy()``, or for direct digest-style reads.
    """
    h = hashlib.new(algorithm)
    h.update(calculate_callable_fullname(fn).encode())
    if use_bytecode:
        h.update(get_callable_bytecode(fn))
    return h
