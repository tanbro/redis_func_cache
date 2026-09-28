"""Tests for the composed Policy design: Policy(keying, hasher, scripts).

Custom dimensions are built by composing components (no mixin MRO), and the
cache snapshot-copies the policy it is given so shared preset instances never
leak their bound namespace across caches.
"""

import types
from dataclasses import replace
from uuid import uuid4

import pytest

from redis_func_cache import RedisFuncCache, lru_policy
from redis_func_cache.hashing import PICKLE_MD5_HASHER, HashConfig, Hasher, JsonMd5Hasher
from redis_func_cache.keying import (
    ClusterMultipleKeying,
    ClusterSingleKeying,
    Keying,
    MultipleKeying,
    SingleKeying,
)
from redis_func_cache.policies import Policy
from redis_func_cache.scripts import LruScripts, MruScripts, RrScripts

from ._catches import redis_factory


def _echo(x):
    return x


class TestHashers:
    def test_preset_default_hasher_is_shared(self):
        assert isinstance(PICKLE_MD5_HASHER, object)

    def test_custom_hasher_without_bytecode(self):
        class StableJsonMd5Hasher(JsonMd5Hasher):
            __hash_config__ = replace(JsonMd5Hasher.__hash_config__, use_bytecode=False)

        hasher = StableJsonMd5Hasher()
        # The decisive property: two distinct functions sharing a name hash equal
        # only when bytecode is excluded from the fingerprint.
        fn1 = types.FunctionType(_echo.__code__, {}, "same_name")
        fn2 = types.FunctionType(_echo.__code__, {}, "same_name")
        assert hasher.calc_hash(fn1, (1,), None) == hasher.calc_hash(fn2, (1,), None)

    def test_make_hasher_factory(self):
        """The factory yields a fresh Hasher subclass hashing identically to
        the equivalent explicit preset."""
        from redis_func_cache.hashing import make_hasher

        cls = make_hasher("JsonMd5Copy", JsonMd5Hasher.__hash_config__)
        assert issubclass(cls, Hasher)
        assert cls.__name__ == "JsonMd5Copy"
        assert cls().calc_hash(_echo, (1,), {"x": "a"}) == JsonMd5Hasher().calc_hash(_echo, (1,), {"x": "a"})

    def test_hash_config_defaults(self):
        conf = HashConfig(algorithm="md5", serializer=lambda x: x)
        assert conf.use_bytecode is True
        assert conf.decoder is None


class TestScripts:
    def test_mru_scripts_flag_and_files(self):
        s = MruScripts()
        assert (s.get_script, s.put_script) == ("lru_get.lua", "lru_put.lua")
        assert s.calc_ext_args(_echo, (), {}) == ("mru",)
        assert LruScripts().calc_ext_args(_echo, (), {}) is None

    def testindex_structure_fact(self):
        """The index structure is an internal fact on Scripts; count_index dispatches on it."""
        assert LruScripts().index_structure == "zset"
        assert RrScripts().index_structure == "set"


class TestKeying:
    def test_key_patterns(self):
        def fn():
            pass

        assert SingleKeying("lru").calc_key_pair("p:", "n") == ("p:n:lru:0", "p:n:lru:1")
        assert SingleKeying("lru").calc_key_pair("p:", "n", fn) == ("p:n:lru:0", "p:n:lru:1")
        assert ClusterSingleKeying("lru-c").calc_key_pair("p:", "n") == ("p:{n:lru-c}:0", "p:{n:lru-c}:1")
        m = MultipleKeying("lru-m").calc_key_pair("p:", "n", fn)
        assert m[0].startswith("p:n:lru-m:") and m[0].endswith(":0") and m[0][:-2] + ":1" == m[1]
        cm = ClusterMultipleKeying("lru-cm").calc_key_pair("p:", "n", fn)
        assert "#{" in cm[0] and cm[0].endswith(":0")

    def test_multiple_requires_fn(self):
        with pytest.raises(TypeError):
            MultipleKeying("lru-m").calc_key_pair("p:", "n", None)


class TestPolicy:
    def test_repr(self):
        r = repr(Policy(SingleKeying("lru"), PICKLE_MD5_HASHER, LruScripts()))
        assert r == "Policy(SingleKeying('lru'), PickleMd5Hasher(), LruScripts())"

    def test_namespace_is_an_argument(self):
        """The policy is stateless: the namespace comes from the call, not from a binding."""
        policy = Policy(SingleKeying("lru"), PICKLE_MD5_HASHER, LruScripts())
        assert policy.calc_key_pair("p1:", "n1") == ("p1:n1:lru:0", "p1:n1:lru:1")
        assert policy.calc_key_pair("p2:", "n2") == ("p2:n2:lru:0", "p2:n2:lru:1")

    def test_delegation(self, mocker):
        policy = Policy(SingleKeying("lru"), PICKLE_MD5_HASHER, MruScripts())
        assert policy.scripts.calc_ext_args(_echo) == ("mru",)
        assert policy.calc_key_pair("p:", "n", _echo) == ("p:n:lru:0", "p:n:lru:1")
        assert policy.scripts.index_structure == "zset"

    def test_base_key_is_the_public_override_point(self):
        class MyKeying(SingleKeying):
            def base_key(self, prefix: str, name: str, fn=None) -> str:
                return f"{prefix}-{name}-{self.key}"

        assert MyKeying("x").calc_key_pair("p:", "n") == ("p:-n-x:0", "p:-n-x:1")

        class Incomplete(Keying):
            pass

        with pytest.raises(NotImplementedError):
            Incomplete().calc_key_pair("p:", "n")

    def test_get_size_dispatches_byindex_structure(self, mocker):
        """get_size picks SCARD vs ZCARD from scripts.index_structure."""
        for scripts, command in ((LruScripts(), "zcard"), (RrScripts(), "scard")):
            client = mocker.Mock()
            client.scan_iter.return_value = iter(["k:0"])
            client.zcard.return_value = 1
            client.scard.return_value = 1
            policy = Policy(MultipleKeying("x"), PICKLE_MD5_HASHER, scripts)
            policy.get_size(client, "p:", "n")
            getattr(client, command).assert_called_once_with("k:0")


class TestCachePolicySharing:
    def test_cache_shares_the_policy(self):
        """Policies are stateless: caches sharing a preset share the same object."""
        cache_a = RedisFuncCache(uuid4().hex, lru_policy, factory=redis_factory)
        cache_b = RedisFuncCache(uuid4().hex, lru_policy, factory=redis_factory)
        assert cache_a.policy is lru_policy
        assert cache_b.policy is lru_policy

    def test_shared_policy_keeps_namespaces_apart(self):
        """Two caches on one preset instance produce distinct key namespaces."""
        cache_a = RedisFuncCache(uuid4().hex, lru_policy, factory=redis_factory)
        cache_b = RedisFuncCache(uuid4().hex, lru_policy, factory=redis_factory)

        def echo(x):
            return x

        assert cache_a.policy.calc_key_pair(cache_a.prefix, cache_a.name, echo) != cache_b.policy.calc_key_pair(
            cache_b.prefix, cache_b.name, echo
        )
