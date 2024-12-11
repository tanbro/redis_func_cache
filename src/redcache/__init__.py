from . import _version as version
from ._version import __version__, __version_tuple__
from .policies import FifoPolicy, LfuPolicy, LruPolicy, MruPolicy, RrPolicy
from .types import AbstractPolicy, RedCache
