from ..mixins.md5hash import Md5PickleMixin
from ..mixins.policies import LfuScriptsMixin, MruExtArgsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = ("MruPolicy", "MruMultiplePolicy", "MruClusterPolicy", "MruClusterMultiplePolicy")


class MruPolicy(LfuScriptsMixin, MruExtArgsMixin, Md5PickleMixin, BaseSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis, with Most Recently Used eviction policy."""

    __name__ = "mru"


class MruMultiplePolicy(LfuScriptsMixin, MruExtArgsMixin, Md5PickleMixin, BaseMultiplePolicy):
    """Each function is cached in its own sorted-set/hash-map pair of redis, with Most Recently Used eviction policy."""

    __name__ = "mru-m"


class MruClusterPolicy(LfuScriptsMixin, MruExtArgsMixin, Md5PickleMixin, BaseClusterSinglePolicy):
    """All functions are cached in a single sorted-set/hash-map pair of redis with cluster support, with Most Recently Used eviction policy."""

    __name__ = "mru-c"


class MruClusterMultiplePolicy(LfuScriptsMixin, MruExtArgsMixin, Md5PickleMixin, BaseClusterMultiplePolicy):
    """Each function is cached in its own sorted-set/hash-map pair of redis with cluster support, with Most Recently Used eviction policy."""

    __name__ = "mru-cm"
