"""Least Recently Used cache policies."""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import LruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LruPolicy", "LruMultiplePolicy", "LruClusterPolicy", "LruClusterMultiplePolicy")


class LruPolicy(LruScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """All decorated functions share the same key pair, use Least Recently Used eviction policy.

    .. inheritance-diagram:: LruPolicy
    """

    __key__ = "lru"


class LruMultiplePolicy(LruScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """Each decorated function of the policy has its own key pair, use Least Recently Used eviction policy.

    .. inheritance-diagram:: LruMultiplePolicy
    """

    __key__ = "lru-m"


class LruClusterPolicy(LruScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """All decorated functions share the same key pair, with cluster support, use Least Recently Used eviction policy.

    .. inheritance-diagram:: LruClusterPolicy
    """

    __key__ = "lru-c"


class LruClusterMultiplePolicy(LruScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """Each decorated function of the policy has its own key pair, with cluster support, use Least Recently Used eviction policy.

    inheritance-diagram:: LruClusterMultiplePolicy
    """

    __key__ = "lru-cm"
