"""FIFO policies"""

from ..mixins.hash import PickleMd5HashMixin
from ..mixins.scripts import FifoScriptsMixin, FifoTScriptsMixin
from .base import BaseClusterMultiplePolicy, BaseClusterSinglePolicy, BaseMultiplePolicy, BaseSinglePolicy

__all__ = (
    "FifoPolicy",
    "FifoClusterPolicy",
    "FifoClusterMultiplePolicy",
    "FifoMultiplePolicy",
    "FifoTPolicy",
    "FifoTClusterPolicy",
    "FifoTClusterMultiplePolicy",
    "FifoTMultiplePolicy",
)


class FifoPolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    FIFO eviction policy, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "fifo"


class FifoMultiplePolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    FIFO eviction policy, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "fifo-m"


class FifoClusterPolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    FIFO eviction policy with Redis cluster support, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "fifo-c"


class FifoClusterMultiplePolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    FIFO eviction policy with Redis cluster support, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "fifo-cm"


class FifoTPolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    FIFO eviction policy (timestamp variant), single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "fifo_t"


class FifoTMultiplePolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    FIFO eviction policy (timestamp variant), multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "fifo_t-m"


class FifoTClusterPolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    FIFO eviction policy (timestamp variant) with Redis cluster support, single key pair.

    All decorated functions share the same Redis key pair.
    """

    __key__ = "fifo_t-c"


class FifoTClusterMultiplePolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    FIFO eviction policy (timestamp variant) with Redis cluster support, multiple key pairs.

    Each decorated function has its own Redis key pair.
    """

    __key__ = "fifo_t-cm"
