"""Least Recently Used cache policies."""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.scripts import LruScriptsMixin, LruTScriptsMixin
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
    LRU eviction policy, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lru"


class LruMultiplePolicy(LruScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    LRU eviction policy, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lru-m"


class LruClusterPolicy(LruScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    LRU eviction policy with Redis cluster support, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lru-c"


class LruClusterMultiplePolicy(LruScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    LRU eviction policy with Redis cluster support, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lru-cm"


class LruTPolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    LRU-T (timestamp-based pseudo LRU) eviction policy, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lru_t"


class LruTMultiplePolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    LRU-T (timestamp-based pseudo LRU) eviction policy, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lru_t-m"


class LruTClusterPolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    LRU-T (timestamp-based pseudo LRU) eviction policy with Redis cluster support, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lru_t-c"


class LruTClusterMultiplePolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    LRU-T (timestamp-based pseudo LRU) eviction policy with Redis cluster support, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lru_t-cm"
