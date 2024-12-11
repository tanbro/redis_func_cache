"""Base class for single-pair cache."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence

if sys.version_info < (3, 12):  # pragma: no cover
    from typing_extensions import override
else:  # pragma: no cover
    from typing import override

if TYPE_CHECKING:
    from redis.typing import KeyT

from ..types import AbstractPolicy

__all__ = ["SinglePolicy"]


class SinglePolicy(AbstractPolicy):
    """An abstract policy class for single sorted-set/hash-map key pair."""

    __name__: str

    @override
    def calculate_keys(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Sequence[KeyT]:
        k = f"{self.cache.prefix}{self.cache.name}:{self.__name__}"
        return f"{k}:0", f"{k}:1"

    @override
    def purge(self) -> int:
        rc = self.cache.get_redis_client()
        return rc.delete(*self.calculate_keys())
