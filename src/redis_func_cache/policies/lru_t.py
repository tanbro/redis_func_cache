from ..mixins.hash import PickleMd5HashMixin
from ..mixins.policies import LruTScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("LruTPolicy", "LruTMultiplePolicy", "LruTClusterPolicy", "LruTClusterMultiplePolicy")


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
