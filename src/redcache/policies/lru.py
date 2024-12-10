from __future__ import annotations

import pickle
import sys
from hashlib import md5
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence, Tuple

if sys.version_info < (3, 9):  # noqa
    import importlib_resources  # type: ignore
else:  # noqa
    import importlib.resources as importlib_resources  # type: ignore


if sys.version_info < (3, 12):  # pragma: no cover
    from typing_extensions import override
else:  # pragma: no cover
    from typing import override


if TYPE_CHECKING:
    from redis.typing import KeyT

from ..types import AbstractPolicy
from ..utils import get_fullname, get_source


class LruPolicy(AbstractPolicy):
    """All functions are cached in a sorted-set/hash-map pair of redis, with Least Recently Used eviction policy."""

    @override
    def calculate_keys(
        self, f: Callable, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None
    ) -> Sequence[KeyT]:
        k = f"{self.cache.prefix}{self.cache.name}:lru"
        return f"{k}:0", f"{k}:1"

    @override
    def calculate_hash(self, f: Callable, args: Optional[Sequence] = None, kwds: Optional[Mapping[str, Any]] = None) -> str:
        h = md5(get_fullname(f).encode())
        source = get_source(f)
        if source is not None:
            h.update(source.encode())
        if args is not None:
            h.update(pickle.dumps(args))
        if kwds is not None:
            h.update(pickle.dumps(kwds))
        return h.hexdigest()

    @override
    def read_lua_scripts(self) -> Tuple[str, str]:
        dir_ = importlib_resources.files(__package__).joinpath("..", "lua")
        return dir_.joinpath("lru_get.lua").read_text(), dir_.joinpath("lru_put.lua").read_text()
