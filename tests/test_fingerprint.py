"""Tests for the callable fingerprint cache in :mod:`redis_func_cache.fingerprint`.

These guard the invariants the optimization relies on: incremental seeding of a
hash object is byte-identical to hashing the whole input at once, the cached
object is shared but never mutated, and both the hash mixins and the multiple
policies feed from the same cache entries.
"""

import hashlib
from base64 import b64encode

from redis_func_cache.fingerprint import hash_fingerprint
from redis_func_cache.mixins.hash import JsonMd5HexHashMixin
from redis_func_cache.utils import calculate_callable_fullname, get_callable_bytecode

from ._catches import MULTI_CACHES


def _echo(x):
    return x


def _reference_fingerprint(algorithm: str, use_bytecode: bool, fn) -> bytes:
    """Compute the fingerprint from scratch, without any caching."""
    h = hashlib.new(algorithm)
    h.update(calculate_callable_fullname(fn).encode())
    if use_bytecode:
        h.update(get_callable_bytecode(fn))
    return h.digest()


def test_seeded_copy_matches_full_computation():
    """copy() of the cached fingerprint, extended with args/kwds, must equal a
    from-scratch hash of fingerprint + arguments."""
    mixin = JsonMd5HexHashMixin()
    conf = mixin.__hash_config__
    got = mixin.calc_hash(_echo, (1,), {"x": "中文"})
    h = hashlib.new(conf.algorithm)
    h.update(calculate_callable_fullname(_echo).encode())
    h.update(get_callable_bytecode(_echo))
    h.update(conf.serializer((1,)))
    h.update(conf.serializer({"x": "中文"}))
    assert got == conf.decoder(h)


def test_cached_object_is_shared_and_unmutated():
    """The same (algorithm, use_bytecode, fn) must return the same cached object,
    and digest-style reads must not consume it."""
    h1 = hash_fingerprint("md5", True, _echo)
    h2 = hash_fingerprint("md5", True, _echo)
    assert h1 is h2

    before = h1.digest()
    assert h1.digest() == before  # digest() is non-destructive
    copy = h1.copy()
    copy.update(b"more data")
    assert h1.digest() == before  # the cached object is untouched by copies


def test_cache_key_is_exactly_the_consumed_fields():
    """Entries are keyed by (algorithm, use_bytecode, fn): different bytecode
    flags produce different objects, everything else shares."""
    assert hash_fingerprint("md5", True, _echo) is not hash_fingerprint("md5", False, _echo)
    assert hash_fingerprint("sha1", True, _echo) is not hash_fingerprint("md5", True, _echo)


def test_fingerprint_shared_between_mixin_and_policy():
    """A multiple policy's calc_keys checksum must hit the same cache entry the
    hash mixin seeded."""
    cache = MULTI_CACHES["lru"]
    policy = cache.policy

    before = hash_fingerprint.cache_info().hits
    JsonMd5HexHashMixin().calc_hash(_echo, (1,), None)
    policy.calc_keys(fn=_echo, args=(), kwds={})
    assert hash_fingerprint.cache_info().hits >= before + 1


def test_multiple_policy_key_contains_b64_checksum():
    """The key pair must embed fullname#<base64 md5 fingerprint>, unpadded."""
    cache = MULTI_CACHES["lru"]
    keys = cache.policy.calc_keys(fn=_echo, args=(), kwds={})
    fullname = calculate_callable_fullname(_echo)
    checksum = b64encode(_reference_fingerprint("md5", True, _echo)).rstrip(b"=").decode()
    for key in keys:
        assert key.startswith(f"{cache.prefix}{cache.name}:")
        assert f"{fullname}#{checksum}:" in key
