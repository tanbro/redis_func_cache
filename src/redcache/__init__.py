from . import _version as version
from ._version import __version__, __version_tuple__
from .policies.fifo import FifoPolicy
from .policies.lfu import LfuPolicy
from .policies.lru import LruClusterMultiplePolicy, LruClusterPolicy, LruMultiplePolicy, LruPolicy
from .policies.mru import MruPolicy
from .policies.rr import RrPolicy
from .types import AbstractPolicy, RedCache
