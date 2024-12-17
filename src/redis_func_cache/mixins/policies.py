"""Some mixins for policies."""

__all__ = (
    "FifoScriptsMixin",
    "LfuScriptsMixin",
    "LruScriptsMixin",
    "MruScriptsMixin",
    "RrScriptsMixin",
    "TLruScriptsMixin",
)


class FifoScriptsMixin:
    """Scripts mixin for fifo policy."""

    __scripts__ = "fifo_get.lua", "fifo_put.lua"


class LfuScriptsMixin:
    """Scripts mixin for lfu policy."""

    __scripts__ = "lfu_get.lua", "lfu_put.lua"


class LruScriptsMixin:
    """Scripts mixin for lru policy."""

    __scripts__ = "lru_get.lua", "lru_put.lua"


MruScriptsMixin = LruScriptsMixin


class TLruScriptsMixin:
    """Scripts mixin for tlru policy."""

    __scripts__ = "tlru_get.lua", "tlru_put.lua"


class RrScriptsMixin:
    """Scripts mixin for rr policy."""

    __scripts__ = "rr_get.lua", "rr_put.lua"
