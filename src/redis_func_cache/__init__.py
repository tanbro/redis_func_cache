from . import _version as version
from ._version import __version__, __version_tuple__
from .cache import RedisFuncCache
from .policies.fifo import (
    fifo_cluster_multiple_policy,
    fifo_cluster_policy,
    fifo_multiple_policy,
    fifo_policy,
    fifo_t_cluster_multiple_policy,
    fifo_t_cluster_policy,
    fifo_t_multiple_policy,
    fifo_t_policy,
)
from .policies.gdsf import (
    gdsf_cluster_multiple_policy,
    gdsf_cluster_policy,
    gdsf_multiple_policy,
    gdsf_policy,
)
from .policies.hyperbolic import (
    hyperbolic_cluster_multiple_policy,
    hyperbolic_cluster_policy,
    hyperbolic_multiple_policy,
    hyperbolic_policy,
)
from .policies.lfu import lfu_cluster_multiple_policy, lfu_cluster_policy, lfu_multiple_policy, lfu_policy
from .policies.lru import (
    lru_cluster_multiple_policy,
    lru_cluster_policy,
    lru_multiple_policy,
    lru_policy,
    lru_t_cluster_multiple_policy,
    lru_t_cluster_policy,
    lru_t_multiple_policy,
    lru_t_policy,
    lru_tr_cluster_multiple_policy,
    lru_tr_cluster_policy,
    lru_tr_multiple_policy,
    lru_tr_policy,
)
from .policies.mru import mru_cluster_multiple_policy, mru_cluster_policy, mru_multiple_policy, mru_policy
from .policies.rr import rr_cluster_multiple_policy, rr_cluster_policy, rr_multiple_policy, rr_policy

__all__ = (
    "RedisFuncCache",
    "__version__",
    "__version_tuple__",
    "fifo_cluster_multiple_policy",
    "fifo_cluster_policy",
    "fifo_multiple_policy",
    "fifo_policy",
    "fifo_t_cluster_multiple_policy",
    "fifo_t_cluster_policy",
    "fifo_t_multiple_policy",
    "fifo_t_policy",
    "gdsf_cluster_multiple_policy",
    "gdsf_cluster_policy",
    "gdsf_multiple_policy",
    "gdsf_policy",
    "hyperbolic_cluster_multiple_policy",
    "hyperbolic_cluster_policy",
    "hyperbolic_multiple_policy",
    "hyperbolic_policy",
    "lfu_cluster_multiple_policy",
    "lfu_cluster_policy",
    "lfu_multiple_policy",
    "lfu_policy",
    "lru_cluster_multiple_policy",
    "lru_cluster_policy",
    "lru_multiple_policy",
    "lru_policy",
    "lru_t_cluster_multiple_policy",
    "lru_t_cluster_policy",
    "lru_t_multiple_policy",
    "lru_t_policy",
    "lru_tr_cluster_multiple_policy",
    "lru_tr_cluster_policy",
    "lru_tr_multiple_policy",
    "lru_tr_policy",
    "mru_cluster_multiple_policy",
    "mru_cluster_policy",
    "mru_multiple_policy",
    "mru_policy",
    "rr_cluster_multiple_policy",
    "rr_cluster_policy",
    "rr_multiple_policy",
    "rr_policy",
    "version",
)
