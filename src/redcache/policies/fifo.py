from ..mixins.md5hash import Md5HashMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("FifoPolicy", "FifoClusterPolicy", "FifoClusterMultiplePolicy", "FifoMultiplePolicy")


class FifoPolicy(Md5HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use First In First Out eviction policy."""

    __name__ = "fifo"
    __scripts__ = "fifo_get.lua", "fifo_put.lua"


class FifoMultiplePolicy(Md5HashMixin, BaseMultiplePolicy):
    """Each decorated function has its own key pair, use First In First Out eviction policy."""

    __name__ = "fifo-m"
    __scripts__ = "fifo_get.lua", "fifo_put.lua"


class FifoClusterPolicy(Md5HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use First In First Out eviction policy."""

    __name__ = "fifo-c"
    __scripts__ = "fifo_get.lua", "fifo_put.lua"


class FifoClusterMultiplePolicy(Md5HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function has its own key pair, with cluster support, use First In First Out eviction policy."""

    __name__ = "fifo-cm"
    __scripts__ = "fifo_get.lua", "fifo_put.lua"
