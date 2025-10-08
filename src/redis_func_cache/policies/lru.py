"""Least Recently Used eviction cache policies."""

from typing import final

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


@final
class LruPolicy(LruScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    LRU eviction policy, single key pair.

    .. inheritance-diagram:: LruPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lru"


@final
class LruMultiplePolicy(LruScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    LRU eviction policy, multiple key pairs.

    .. inheritance-diagram:: LruMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lru-m"


@final
class LruClusterPolicy(LruScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    LRU eviction policy with Redis cluster support, single key pair.

    .. inheritance-diagram:: LruClusterPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lru-c"


@final
class LruClusterMultiplePolicy(LruScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    LRU eviction policy with Redis cluster support, multiple key pairs.

    .. inheritance-diagram:: LruClusterMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lru-cm"


@final
class LruTPolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    LRU-T (timestamp-based pseudo LRU) eviction policy, single key pair.

    .. inheritance-diagram:: LruTPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lru_t"


@final
class LruTMultiplePolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    LRU-T (timestamp-based pseudo LRU) eviction policy, multiple key pairs.

    .. inheritance-diagram:: LruTMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lru_t-m"


@final
class LruTClusterPolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    LRU-T (timestamp-based pseudo LRU) eviction policy with Redis cluster support, single key pair.

    .. inheritance-diagram:: LruTClusterPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "lru_t-c"


@final
class LruTClusterMultiplePolicy(LruTScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    LRU-T (timestamp-based pseudo LRU) eviction policy with Redis cluster support, multiple key pairs.

    .. inheritance-diagram:: LruTClusterMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "lru_t-cm"
