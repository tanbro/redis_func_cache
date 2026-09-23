"""Tests for the mixin class factories :func:`make_hash_mixin` and :func:`make_scripts_mixin`.

These guard the factory contract: the generated class carries the given config,
produces hashes identical to the equivalent built-in mixin, and each call returns
a fresh class (no memoization, by design — see docs/design/hash-mixin-factory.md).
"""

import hashlib
import pickle

from redis_func_cache.mixins.hash import (
    HEX_DIGEST_DECODER,
    JSON_SERIALIZER,
    AbstractHashMixin,
    HashConfig,
    JsonMd5HexHashMixin,
    make_hash_mixin,
)
from redis_func_cache.mixins.scripts import AbstractScriptsMixin, LruScriptsMixin, make_scripts_mixin
from redis_func_cache.utils import calculate_callable_fullname, get_callable_bytecode


def _echo(x):
    return x


class TestMakeHashMixin:
    def test_generated_class_carries_config(self):
        conf = HashConfig(algorithm="sha256", serializer=pickle.dumps, decoder=HEX_DIGEST_DECODER)
        cls = make_hash_mixin("PickleSha256HexHashMixin", conf)
        assert issubclass(cls, AbstractHashMixin)
        assert cls.__name__ == "PickleSha256HexHashMixin"
        assert cls.__hash_config__ is conf

    def test_output_matches_equivalent_builtin_mixin(self):
        """A factory-built class with the standard parts must hash exactly like
        the hand-written class with the same combination."""
        factory_cls = make_hash_mixin(
            "JsonMd5Hex", HashConfig(algorithm="md5", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)
        )
        builtin = JsonMd5HexHashMixin()
        assert factory_cls().calc_hash(_echo, (1,), {"x": "中文"}) == builtin.calc_hash(_echo, (1,), {"x": "中文"})

    def test_each_call_returns_fresh_class(self):
        """No memoization: equal configs yield distinct classes that are not
        isinstance-compatible with each other, but both satisfy the abstract base."""
        conf = HashConfig(algorithm="md5", serializer=pickle.dumps)
        cls1 = make_hash_mixin("A", conf)
        cls2 = make_hash_mixin("B", conf)
        assert cls1 is not cls2
        assert not issubclass(cls2, cls1)
        assert not isinstance(cls1(), cls2)
        assert isinstance(cls1(), AbstractHashMixin) and isinstance(cls2(), AbstractHashMixin)

    def test_custom_base(self):
        class MyBase(AbstractHashMixin):
            __hash_config__ = HashConfig(algorithm="md5", serializer=pickle.dumps)

            def extra(self):
                return "extra"

        conf = HashConfig(algorithm="sha1", serializer=JSON_SERIALIZER)
        cls = make_hash_mixin("WithBase", conf, base=MyBase)
        assert issubclass(cls, MyBase)
        instance = cls()
        assert instance.extra() == "extra"
        assert instance.__hash_config__ is conf

    def test_fresh_config_not_shared_between_instances(self):
        cls = make_hash_mixin("C", HashConfig(algorithm="md5", serializer=pickle.dumps))
        assert cls() is not cls()
        assert cls().__hash_config__ is cls().__hash_config__


class TestMakeScriptsMixin:
    def test_generated_class_carries_scripts(self):
        cls = make_scripts_mixin("MyScripts", ("my_get.lua", "my_put.lua"))
        assert issubclass(cls, AbstractScriptsMixin)
        assert cls.__name__ == "MyScripts"
        assert cls.__scripts__ == ("my_get.lua", "my_put.lua")

    def test_each_call_returns_fresh_class(self):
        cls1 = make_scripts_mixin("S1", ("a.lua", "b.lua"))
        cls2 = make_scripts_mixin("S2", ("a.lua", "b.lua"))
        assert cls1 is not cls2
        assert not isinstance(cls1(), cls2)
        assert isinstance(cls1(), AbstractScriptsMixin) and isinstance(cls2(), AbstractScriptsMixin)

    def test_custom_base(self):
        class MyBase(AbstractScriptsMixin):
            __scripts__ = "x.lua", "y.lua"

            def extra(self):
                return "extra"

        cls = make_scripts_mixin("WithBase", ("my_get.lua", "my_put.lua"), base=MyBase)
        assert issubclass(cls, MyBase)
        instance = cls()
        assert instance.extra() == "extra"
        assert instance.__scripts__ == ("my_get.lua", "my_put.lua")

    def test_builtins_unaffected(self):
        assert LruScriptsMixin.__scripts__ == ("lru_get.lua", "lru_put.lua")


def test_generated_hash_matches_reference_computation():
    """The generated class's output equals a from-scratch md5 of the same inputs."""
    conf = HashConfig(algorithm="md5", serializer=JSON_SERIALIZER, decoder=HEX_DIGEST_DECODER)
    got = make_hash_mixin("Ref", conf)().calc_hash(_echo, (1,), None)
    h = hashlib.new("md5")
    h.update(calculate_callable_fullname(_echo).encode())
    h.update(get_callable_bytecode(_echo))
    h.update(conf.serializer((1,)))
    assert got == HEX_DIGEST_DECODER(h)
