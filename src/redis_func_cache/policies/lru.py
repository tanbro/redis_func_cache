"""Least Recently Used eviction cache policies."""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import LruScripts, LruTScripts
from . import Policy

__all__ = (
    "lru_cluster_multiple_policy",
    "lru_cluster_policy",
    "lru_multiple_policy",
    "lru_policy",
    "lru_t_cluster_multiple_policy",
    "lru_t_cluster_policy",
    "lru_t_multiple_policy",
    "lru_t_policy",
)

#: LRU eviction policy, single key pair shared by all decorated functions.
lru_policy = Policy(SingleKeying("lru"), PICKLE_MD5_HASHER, LruScripts())
#: LRU eviction policy, one key pair per decorated function.
lru_multiple_policy = Policy(MultipleKeying("lru-m"), PICKLE_MD5_HASHER, LruScripts())
#: LRU eviction policy with Redis cluster support, single key pair.
lru_cluster_policy = Policy(ClusterSingleKeying("lru-c"), PICKLE_MD5_HASHER, LruScripts())
#: LRU eviction policy with Redis cluster support, one key pair per decorated function.
lru_cluster_multiple_policy = Policy(ClusterMultipleKeying("lru-cm"), PICKLE_MD5_HASHER, LruScripts())

#: LRU-T (timestamp-based pseudo LRU) eviction policy, single key pair.
lru_t_policy = Policy(SingleKeying("lru_t"), PICKLE_MD5_HASHER, LruTScripts())
#: LRU-T (timestamp-based pseudo LRU) eviction policy, one key pair per decorated function.
lru_t_multiple_policy = Policy(MultipleKeying("lru_t-m"), PICKLE_MD5_HASHER, LruTScripts())
#: LRU-T (timestamp-based pseudo LRU) eviction policy with Redis cluster support, single key pair.
lru_t_cluster_policy = Policy(ClusterSingleKeying("lru_t-c"), PICKLE_MD5_HASHER, LruTScripts())
#: LRU-T (timestamp-based pseudo LRU) eviction policy with Redis cluster support, one key pair per function.
lru_t_cluster_multiple_policy = Policy(ClusterMultipleKeying("lru_t-cm"), PICKLE_MD5_HASHER, LruTScripts())
