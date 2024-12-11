from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional, Sequence

if TYPE_CHECKING:
    from redis.typing import EncodableT

if sys.version_info < (3, 12):  # pragma: no cover
    from typing_extensions import override
else:  # pragma: no cover
    from typing import override

from ..mixins import Md5HashMixin
from .abstract import AbstractSinglePolicy

__all__ = ["MruPolicy"]


class MruPolicy(Md5HashMixin, AbstractSinglePolicy):
    """All functions are cached in a sorted-set/hash-map pair of redis, with Most Recently Used eviction policy."""

    __name__ = "mru"
    __scripts__ = "lru_get.lua", "lru_put.lua"

    @override
    def calculate_ext_args(
        self, f: Optional[Callable] = None, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Optional[Iterable[EncodableT]]:
        return ("mru",)
