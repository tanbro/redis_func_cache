from ..mixins.md5hash import Md5PickleMixin
from ..mixins.policies import LruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LruPolicy", "LruMultiplePolicy", "LruClusterPolicy", "LruClusterMultiplePolicy")


class LruPolicy(LruScriptsMixin, Md5PickleMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use Least Recently Used eviction policy."""

    __name__ = "lru"


class LruMultiplePolicy(LruScriptsMixin, Md5PickleMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use Least Recently Used eviction policy."""

    __name__ = "lru-m"


class LruClusterPolicy(LruScriptsMixin, Md5PickleMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use Least Recently Used eviction policy."""

    __name__ = "lru-c"


class LruClusterMultiplePolicy(LruScriptsMixin, Md5PickleMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair, with cluster support, use Least Recently Used eviction policy."""

    __name__ = "lru-cm"
