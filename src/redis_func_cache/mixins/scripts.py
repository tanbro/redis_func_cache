"""Some mixins with lua scripts defined for policies."""

from abc import ABC
from typing import Tuple

__all__ = (
    "AbstractScriptsMixin",
    "FifoScriptsMixin",
    "FifoTScriptsMixin",
    "LfuScriptsMixin",
    "LruScriptsMixin",
    "MruScriptsMixin",
    "RrScriptsMixin",
    "LruTScriptsMixin",
)


class AbstractScriptsMixin(ABC):
    """Abstract scripts mixin.

    .. inheritance-diagram:: AbstractScriptsMixin
        :parts: 1
    """

    __scripts__: Tuple[str, str]


class FifoScriptsMixin(AbstractScriptsMixin):
    """Scripts mixin for fifo policy.

    .. inheritance-diagram:: FifoScriptsMixin
        :parts: 1
    """

    __scripts__ = "fifo_get.lua", "fifo_put.lua"


class FifoTScriptsMixin(AbstractScriptsMixin):
    """Scripts mixin for fifo policy.

    .. inheritance-diagram:: FifoTScriptsMixin
        :parts: 1
    """

    __scripts__ = "fifo_get.lua", "fifo_t_put.lua"


class LfuScriptsMixin(AbstractScriptsMixin):
    """Scripts mixin for lfu policy.

    .. inheritance-diagram:: LfuScriptsMixin
        :parts: 1
    """

    __scripts__ = "lfu_get.lua", "lfu_put.lua"


class LruScriptsMixin(AbstractScriptsMixin):
    """Scripts mixin for lru policy.

    .. inheritance-diagram:: LruScriptsMixin
        :parts: 1
    """

    __scripts__ = "lru_get.lua", "lru_put.lua"


MruScriptsMixin = LruScriptsMixin


class LruTScriptsMixin(AbstractScriptsMixin):
    """Scripts mixin for lru-t policy.

    .. inheritance-diagram:: LruTScriptsMixin
        :parts: 1
    """

    __scripts__ = "lru_t_get.lua", "lru_t_put.lua"


class RrScriptsMixin(AbstractScriptsMixin):
    """Scripts mixin for rr policy.

    .. inheritance-diagram:: RrScriptsMixin
        :parts: 1
    """

    __scripts__ = "rr_get.lua", "rr_put.lua"
