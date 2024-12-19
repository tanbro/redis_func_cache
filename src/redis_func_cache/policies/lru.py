"""Least Recently Used cache policies."""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import LruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LruPolicy", "LruMultiplePolicy", "LruClusterPolicy", "LruClusterMultiplePolicy")


class LruPolicy(LruScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    .. inheritance-diagram:: LruPolicy

    All decorated functions share the same key pair, use Least Recently Used eviction policy.
    """

    __key__ = "lru"


class LruMultiplePolicy(LruScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    .. inheritance-diagram:: LruMultiplePolicy

    Each decorated function of the policy has its own key pair, use Least Recently Used eviction policy.
    """

    __key__ = "lru-m"


class LruClusterPolicy(LruScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    .. inheritance-diagram:: LruClusterPolicy

    All decorated functions share the same key pair, with cluster support, use Least Recently Used eviction policy.
    """

    __key__ = "lru-c"


class LruClusterMultiplePolicy(LruScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    inheritance-diagram:: LruClusterMultiplePolicy

    Each decorated function of the policy has its own key pair, with cluster support, use Least Recently Used eviction policy.
    """

    __key__ = "lru-cm"
