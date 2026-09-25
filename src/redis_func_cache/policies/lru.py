"""Least Recently Used eviction cache policies."""

from ..hashing import PICKLE_MD5_HASHER
from ..keying import ClusterMultipleKeying, ClusterSingleKeying, MultipleKeying, SingleKeying
from ..scripts import LruScripts, LruTScripts
from . import Policy

__all__ = (
    "LruClusterMultiplePolicy",
    "LruClusterPolicy",
    "LruMultiplePolicy",
    "LruPolicy",
    "LruTClusterMultiplePolicy",
    "LruTClusterPolicy",
    "LruTMultiplePolicy",
    "LruTPolicy",
)

#: LRU eviction policy, single key pair shared by all decorated functions.
LruPolicy = Policy(SingleKeying("lru"), PICKLE_MD5_HASHER, LruScripts())
#: LRU eviction policy, one key pair per decorated function.
LruMultiplePolicy = Policy(MultipleKeying("lru-m"), PICKLE_MD5_HASHER, LruScripts())
#: LRU eviction policy with Redis cluster support, single key pair.
LruClusterPolicy = Policy(ClusterSingleKeying("lru-c"), PICKLE_MD5_HASHER, LruScripts())
#: LRU eviction policy with Redis cluster support, one key pair per decorated function.
LruClusterMultiplePolicy = Policy(ClusterMultipleKeying("lru-cm"), PICKLE_MD5_HASHER, LruScripts())

#: LRU-T (timestamp-based pseudo LRU) eviction policy, single key pair.
LruTPolicy = Policy(SingleKeying("lru_t"), PICKLE_MD5_HASHER, LruTScripts())
#: LRU-T (timestamp-based pseudo LRU) eviction policy, one key pair per decorated function.
LruTMultiplePolicy = Policy(MultipleKeying("lru_t-m"), PICKLE_MD5_HASHER, LruTScripts())
#: LRU-T (timestamp-based pseudo LRU) eviction policy with Redis cluster support, single key pair.
LruTClusterPolicy = Policy(ClusterSingleKeying("lru_t-c"), PICKLE_MD5_HASHER, LruTScripts())
#: LRU-T (timestamp-based pseudo LRU) eviction policy with Redis cluster support, one key pair per function.
LruTClusterMultiplePolicy = Policy(ClusterMultipleKeying("lru_t-cm"), PICKLE_MD5_HASHER, LruTScripts())
