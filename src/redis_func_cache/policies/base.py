"""Base class for single-pair cache."""

from __future__ import annotations

import hashlib
import sys
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence, Tuple
from weakref import CallableProxyType

from redis_func_cache.types import RedisFuncCache

if sys.version_info < (3, 12):  # pragma: no cover
    from typing_extensions import override
else:  # pragma: no cover
    from typing import override

if TYPE_CHECKING:  # pragma: no cover
    from redis.typing import KeyT

from ..types import AbstractPolicy
from ..utils import base64_hash_digest, get_fullname, get_source

__all__ = ("BaseSinglePolicy", "BaseClusterSinglePolicy", "BaseMultiplePolicy", "BaseClusterMultiplePolicy")


class BaseSinglePolicy(AbstractPolicy):
    """Base policy class for single sorted-set/hash-map key pair.
    All decorated functions of the policy share the same key pair.

    Do not use it directly.
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
    def purge(self) -> int:
        rc = self.cache.get_redis_client()
        return rc.delete(*self.calc_keys())

    @override
    def get_size(self) -> int:
        rc = self.cache.get_redis_client()
        return rc.hlen(self.calc_keys()[1])


class BaseClusterSinglePolicy(BaseSinglePolicy):
    """Base policy class for single sorted-set/hash-map key pair, with cluster support.
    All decorated functions of the policy share the same key pair.

    Do not use it directly.
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
    """Base policy class for multiple sorted-set/hash-map key pairs.
    Each decorated function of the policy has its own key pair.

    Do not use it directly.
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
        checksum = base64_hash_digest(h)
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{checksum}"
        return f"{k}:0", f"{k}:1"

    @override
    def purge(self) -> int:
        pat = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:*"
        rc = self.cache.get_redis_client()
        keys = rc.keys(pat)
        if keys:
            return rc.delete(*keys)
        return 0


class BaseClusterMultiplePolicy(BaseMultiplePolicy):
    """Base policy class for multiple sorted-set/hash-map key pairs, with cluster support.
    Each decorated function of the policy has its own key pair.

    Do not use it directly.
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
        checksum = base64_hash_digest(h)
        k = f"{self.cache.prefix}{self.cache.name}:{self.__key__}:{fullname}#{{{checksum}}}"
        return f"{k}:0", f"{k}:1"
