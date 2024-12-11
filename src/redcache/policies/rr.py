from ..mixins.md5hash import Md5HashMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("RrPolicy", "RrMultiplePolicy", "RrClusterPolicy", "RrClusterMultiplePolicy")


class RrPolicy(Md5HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use random replacement eviction policy."""

    __name__ = "rr"
    __scripts__ = "rr_get.lua", "rr_put.lua"


class RrMultiplePolicy(Md5HashMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use random replacement eviction policy."""

    __name__ = "rr-m"
    __scripts__ = "rr_get.lua", "rr_put.lua"


class RrClusterPolicy(Md5HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use random replacement eviction policy."""

    __name__ = "rr-c"
    __scripts__ = "rr_get.lua", "rr_put.lua"


class RrClusterMultiplePolicy(Md5HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair with cluster support, use random replacement eviction policy."""

    __name__ = "rr-cm"
    __scripts__ = "rr_get.lua", "rr_put.lua"
