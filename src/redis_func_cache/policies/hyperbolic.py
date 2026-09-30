"""Hyperbolic (LFU-with-aging) eviction policy.

Score = ``log(freq + 1) / (age + 1) ^ 0.25`` (Hyperbolic Caching, USENIX ATC
2020): one ZSET score captures recency *and* frequency, and stale hot entries
age out without a decay task — the classical LFU weakness this fixes. See
``lua/hyperbolic_put.lua`` for the score contract and its caveats.

.. versionadded:: 1.0
"""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import HyperbolicScripts
from . import Policy

__all__ = (
    "hyperbolic_cluster_multiple_policy",
    "hyperbolic_cluster_policy",
    "hyperbolic_multiple_policy",
    "hyperbolic_policy",
)

#: Hyperbolic eviction policy, single key pair shared by all decorated functions.
hyperbolic_policy = Policy(SingleKeying("hyperbolic"), PICKLE_MD5_HASHER, HyperbolicScripts())
#: Hyperbolic eviction policy, one key pair per decorated function.
hyperbolic_multiple_policy = Policy(MultipleKeying("hyperbolic-m"), PICKLE_MD5_HASHER, HyperbolicScripts())
#: Hyperbolic eviction policy with Redis cluster support, single key pair.
hyperbolic_cluster_policy = Policy(ClusterSingleKeying("hyperbolic-c"), PICKLE_MD5_HASHER, HyperbolicScripts())
#: Hyperbolic eviction policy with Redis cluster support, one key pair per decorated function.
hyperbolic_cluster_multiple_policy = Policy(
    ClusterMultipleKeying("hyperbolic-cm"), PICKLE_MD5_HASHER, HyperbolicScripts()
)
