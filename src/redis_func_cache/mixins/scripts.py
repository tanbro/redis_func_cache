"""Some mixins with lua scripts defined for policies."""

from abc import ABC

__all__ = (
    "AbstractScriptsMixin",
    "FifoScriptsMixin",
    "FifoTScriptsMixin",
    "LfuScriptsMixin",
    "LruScriptsMixin",
    "LruTScriptsMixin",
    "MruScriptsMixin",
    "RrScriptsMixin",
    "make_scripts_mixin",
)


class AbstractScriptsMixin(ABC):
    """Abstract scripts mixin.

    .. inheritance-diagram:: AbstractScriptsMixin
        :parts: 1

    Attributes:
        __scripts__ (tuple[str, str]): A pair of file name for ‘get’ and ‘put’ Lua scripts to be used by the policy.
    """

    __scripts__: tuple[str, str]


def make_scripts_mixin(
    name: str, scripts: tuple[str, str], base: type[AbstractScriptsMixin] | None = None
) -> type[AbstractScriptsMixin]:
    """Create a scripts mixin class from a pair of Lua script file names.

    Args:
        name: Name of the generated class.
        scripts: A pair of file names for the 'get' and 'put' Lua scripts.
        base: Base class to inherit. Default is :class:`.AbstractScriptsMixin`; if given,
            it must be a subclass of :class:`.AbstractScriptsMixin` (or itself define a
            compatible ``__scripts__``).

    Returns:
        A new mixin class. Each call returns a fresh class even for equal ``scripts``:
        instances of two such classes do not satisfy ``isinstance`` checks against each
        other. Compose the mixin once at definition time and target
        :class:`.AbstractScriptsMixin` for type checks.
    """
    return type(name, (AbstractScriptsMixin if base is None else base,), {"__scripts__": scripts})


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
