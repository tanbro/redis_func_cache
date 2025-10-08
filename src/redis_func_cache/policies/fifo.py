"""FIFO eviction policies"""

from typing import final

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


@final
class FifoPolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    FIFO eviction policy, single key pair.

    .. inheritance-diagram:: FifoPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "fifo"


@final
class FifoMultiplePolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    FIFO eviction policy, multiple key pairs.

    .. inheritance-diagram:: FifoMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "fifo-m"


@final
class FifoClusterPolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    FIFO eviction policy with Redis cluster support, single key pair.

    .. inheritance-diagram:: FifoClusterPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "fifo-c"


@final
class FifoClusterMultiplePolicy(FifoScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    FIFO eviction policy with Redis cluster support, multiple key pairs.

    .. inheritance-diagram:: FifoClusterMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "fifo-cm"


@final
class FifoTPolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseSinglePolicy):
    """
    FIFO eviction policy (timestamp variant), single key pair.

    .. inheritance-diagram:: FifoTPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "fifo_t"


@final
class FifoTMultiplePolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseMultiplePolicy):
    """
    FIFO eviction policy (timestamp variant), multiple key pairs.

    .. inheritance-diagram:: FifoTMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "fifo_t-m"


@final
class FifoTClusterPolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseClusterSinglePolicy):
    """
    FIFO eviction policy (timestamp variant) with Redis cluster support, single key pair.

    .. inheritance-diagram:: FifoTClusterPolicy
        :parts: 1

    All decorated functions share the same Redis key pair.
    """

    __key__ = "fifo_t-c"


@final
class FifoTClusterMultiplePolicy(FifoTScriptsMixin, PickleMd5HashMixin, BaseClusterMultiplePolicy):
    """
    FIFO eviction policy (timestamp variant) with Redis cluster support, multiple key pairs.

    .. inheritance-diagram:: FifoTClusterMultiplePolicy
        :parts: 1

    Each decorated function has its own Redis key pair.
    """

    __key__ = "fifo_t-cm"
