from . import _version as version
from ._version import __version__, __version_tuple__
from .cache import RedisFuncCache
from .policies.fifo import (
    FifoClusterMultiplePolicy,
    FifoClusterPolicy,
    FifoMultiplePolicy,
    FifoPolicy,
    FifoTClusterMultiplePolicy,
    FifoTClusterPolicy,
    FifoTMultiplePolicy,
    FifoTPolicy,
)
from .policies.lfu import LfuClusterMultiplePolicy, LfuClusterPolicy, LfuMultiplePolicy, LfuPolicy
from .policies.lru import (
    LruClusterMultiplePolicy,
    LruClusterPolicy,
    LruMultiplePolicy,
    LruPolicy,
    LruTClusterMultiplePolicy,
    LruTClusterPolicy,
    LruTMultiplePolicy,
    LruTPolicy,
)
from .policies.mru import MruClusterMultiplePolicy, MruClusterPolicy, MruMultiplePolicy, MruPolicy
from .policies.rr import RrClusterMultiplePolicy, RrClusterPolicy, RrMultiplePolicy, RrPolicy
