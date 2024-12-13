from ..mixins.hash import PickleMd5Base64HashMixin
from ..mixins.policies import LruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LruPolicy", "LruMultiplePolicy", "LruClusterPolicy", "LruClusterMultiplePolicy")


class LruPolicy(LruScriptsMixin, PickleMd5Base64HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use Least Recently Used eviction policy."""

    __key__ = "lru"


class LruMultiplePolicy(LruScriptsMixin, PickleMd5Base64HashMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use Least Recently Used eviction policy."""

    __key__ = "lru-m"


class LruClusterPolicy(LruScriptsMixin, PickleMd5Base64HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use Least Recently Used eviction policy."""

    __key__ = "lru-c"


class LruClusterMultiplePolicy(LruScriptsMixin, PickleMd5Base64HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair, with cluster support, use Least Recently Used eviction policy."""

    __key__ = "lru-cm"
