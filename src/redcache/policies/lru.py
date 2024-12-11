from ..mixins.md5hash import Md5HashMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LruPolicy", "LruMultiplePolicy", "LruClusterPolicy", "LruClusterMultiplePolicy")


class LruPolicy(Md5HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use Least Recently Used eviction policy."""

    __name__ = "lru"
    __scripts__ = "lru_get.lua", "lru_put.lua"


class LruMultiplePolicy(Md5HashMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use Least Recently Used eviction policy."""

    __name__ = "lru-m"
    __scripts__ = "lru_get.lua", "lru_put.lua"


class LruClusterPolicy(Md5HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use Least Recently Used eviction policy."""

    __name__ = "lru-c"
    __scripts__ = "lru_get.lua", "lru_put.lua"


class LruClusterMultiplePolicy(Md5HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair, with cluster support, use Least Recently Used eviction policy."""

    __name__ = "lru-cm"
    __scripts__ = "lru_get.lua", "lru_put.lua"
