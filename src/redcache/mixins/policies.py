"""Some mixins for policies."""

__all__ = ("FifoScriptsMixin", "LfuScriptsMixin", "LruScriptsMixin", "RrScriptsMixin", "MruExtArgsMixin")


class FifoScriptsMixin:
    __scripts__ = "fifo_get.lua", "fifo_put.lua"


class LfuScriptsMixin:
    __scripts__ = "lfu_get.lua", "lfu_put.lua"


class LruScriptsMixin:
    __scripts__ = "lru_get.lua", "lru_put.lua"


class RrScriptsMixin:
    __scripts__ = "rr_get.lua", "rr_put.lua"


class MruExtArgsMixin:
    def calc_ext_args(self, *args, **kwargs):
        return ("mru",)
