from ..mixins.hash import PickleMd5Base64HashMixin
from ..mixins.policies import MruExtArgsMixin, MruScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("MruPolicy", "MruMultiplePolicy", "MruClusterPolicy", "MruClusterMultiplePolicy")


class MruPolicy(MruScriptsMixin, MruExtArgsMixin, PickleMd5Base64HashMixin, BaseSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis, with Most Recently Used eviction policy."""

    __key__ = "mru"


class MruMultiplePolicy(MruScriptsMixin, MruExtArgsMixin, PickleMd5Base64HashMixin, BaseMultiplePolicy):
    """Each function is cached in its own sorted-set/hash-map pair of redis, with Most Recently Used eviction policy."""

    __key__ = "mru-m"


class MruClusterPolicy(MruScriptsMixin, MruExtArgsMixin, PickleMd5Base64HashMixin, BaseClusterSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis with cluster support, with Most Recently Used eviction policy."""

    __key__ = "mru-c"


class MruClusterMultiplePolicy(MruScriptsMixin, MruExtArgsMixin, PickleMd5Base64HashMixin, BaseClusterMultiplePolicy):
    """Each function is cached in its own sorted-set/hash-map pair of redis with cluster support, with Most Recently Used eviction policy."""

    __key__ = "mru-cm"
