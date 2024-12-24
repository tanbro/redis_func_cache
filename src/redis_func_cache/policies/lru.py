"""Least Recently Used cache policies."""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import LruScriptsMixin, LruTScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = (
    "LruPolicy",
    "LruMultiplePolicy",
    "LruClusterPolicy",
    "LruClusterMultiplePolicy",
    "LruTPolicy",
    "LruTMultiplePolicy",
    "LruTClusterPolicy",
    "LruTClusterMultiplePolicy",
)


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


class LruTPolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    .. inheritance-diagram:: LruTPolicy

    All decorated functions share the same key pair, use time based pseudo Least Recently Used eviction policy.
    """

    __key__ = "lru_t"


class LruTMultiplePolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    .. inheritance-diagram:: LruTMultiplePolicy

    Each decorated function of the policy has its own key pair, use time based pseudo Least Recently Used eviction policy.
    """

    __key__ = "lru_t-m"


class LruTClusterPolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    .. inheritance-diagram:: LruTClusterPolicy

    All decorated functions share the same key pair, with cluster support, use time based pseudo Least Recently Used eviction policy.
    """

    __key__ = "lru_t-c"


class LruTClusterMultiplePolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    .. inheritance-diagram:: LruTClusterMultiplePolicy

    Each decorated function of the policy has its own key pair, with cluster support, use time based pseudo Least Recently Used eviction policy.
    """

    __key__ = "lru_t-cm"
