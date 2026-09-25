"""Golden contract tests pinning the observable behavior of every built-in policy.

The fixture ``tests/_golden.json`` was generated from the pre-refactor
(mixin-MRO) implementation (see ``tests/_gen_golden.py``) and freezes:

- the Redis key pair each policy produces for two distinct functions,
- the sub-key hash for fixed inputs,
- the extra ARGV entries (``calc_ext_args``),
- the (get, put) Lua script file names.

These assertions must hold unchanged across the composition refactor
(``Policy(keying, hasher, scripts)``): key naming, hash values and the ARGV
layout are the on-the-wire contract shared with existing Redis data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from redis_func_cache import RedisFuncCache
from redis_func_cache.policies.policy import Policy

from ._golden_fns import fn_a, fn_b

GOLDEN = json.loads((Path(__file__).with_name("_golden.json")).read_text(encoding="utf-8"))

PREFIX, NAME = "gp:", "gn"
ARGS, KWDS = (1,), {"x": "a"}


def _policies() -> list[tuple[str, Policy]]:
    """Collect every built-in policy preset bound to the golden namespace."""
    import redis_func_cache.policies.fifo as fifo_mod
    import redis_func_cache.policies.lfu as lfu_mod
    import redis_func_cache.policies.lru as lru_mod
    import redis_func_cache.policies.mru as mru_mod
    import redis_func_cache.policies.rr as rr_mod

    out: list[tuple[str, Policy]] = []
    for module in (fifo_mod, lfu_mod, lru_mod, mru_mod, rr_mod):
        for attr in dir(module):
            policy = getattr(module, attr)
            if isinstance(policy, Policy):
                policy._bind(PREFIX, NAME)
                out.append((attr, policy))
    assert len(out) == len(GOLDEN)
    return out


class _RecordScript:
    """Stands in for a registered redis Script, recording keys and args."""

    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def __call__(self, keys=None, args=None, client=None):
        self._calls.append({"keys": list(keys), "args": list(args)})


class _RecordingClient:
    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self._calls = calls

    def register_script(self, script):
        return _RecordScript(self._calls)


@pytest.mark.parametrize("policy", _policies(), ids=lambda p: p[0])
class TestGoldenPolicyContract:
    def test_keys(self, policy):
        name, policy = policy
        expected = GOLDEN[name]
        assert list(policy.calc_keys(fn_a, ARGS, KWDS)) == expected["keys_a"]
        assert list(policy.calc_keys(fn_b, ARGS, KWDS)) == expected["keys_b"]

    def test_hash(self, policy):
        name, policy = policy
        assert policy.calc_hash(fn_a, ARGS, KWDS).hex() == GOLDEN[name]["hash"]

    def test_ext_args(self, policy):
        name, policy = policy
        assert list(policy.calc_ext_args(fn_a, ARGS, KWDS) or ()) == GOLDEN[name]["ext_args"]

    def test_scripts(self, policy):
        name, policy = policy
        assert [policy.scripts.get_script, policy.scripts.put_script] == GOLDEN[name]["scripts"]


class TestGoldenArgvLayout:
    """Pin the ARGV layout of get/put: ext_args must land on ARGV[7] of put,
    the reserved options JSON goes last."""

    def test_put_argv(self):
        calls: list[dict[str, Any]] = []
        RedisFuncCache.put(
            _RecordScript(calls),
            keys=("z", "h"),
            hash_value=b"deadbeef",
            value="v",
            maxsize=10,
            update_ttl=True,
            ttl=60,
            field_ttl=30,
            ext_args=("mru",),
        )
        assert calls == [
            {
                "keys": ["z", "h"],
                "args": [10, 1, 60, b"deadbeef", "v", 30, "mru", b"{}"],
            }
        ]

    def test_put_argv_no_ext_args_options_last(self):
        calls: list[dict[str, Any]] = []
        RedisFuncCache.put(
            _RecordScript(calls),
            keys=("z", "h"),
            hash_value=b"deadbeef",
            value="v",
            maxsize=10,
            update_ttl=False,
            ttl=0,
        )
        assert calls[0]["args"] == [10, 0, 0, b"deadbeef", "v", 0, b"{}"]

    def test_get_argv(self):
        calls: list[dict[str, Any]] = []
        RedisFuncCache.get(
            _RecordScript(calls),
            keys=("z", "h"),
            hash_value=b"deadbeef",
            update_ttl=True,
            ttl=60,
            options={"a": 1},
            ext_args=("mru",),
        )
        assert calls[0]["args"][:4] == [1, 60, b"deadbeef", json.dumps({"a": 1}, separators=(",", ":")).encode()]
        assert calls[0]["args"][4:] == ["mru"]

    def test_policy_ext_args_land_on_argv7(self):
        """End-to-end: a policy's ext_args flow into put's ARGV[7]."""
        calls: list[dict[str, Any]] = []
        client = _RecordingClient(calls)
        scripts = tuple(client.register_script(t) for t in ("get", "put"))
        name, policy = _policies()[0]
        keys, hash_value, ext_args = (
            policy.calc_keys(fn_a, ARGS, KWDS),
            policy.calc_hash(fn_a, ARGS, KWDS),
            policy.calc_ext_args(fn_a, ARGS, KWDS) or (),
        )
        RedisFuncCache.put(scripts[1], keys, hash_value, "v", maxsize=10, update_ttl=True, ttl=60, ext_args=ext_args)
        expected_ext = GOLDEN[name]["ext_args"]
        args = calls[0]["args"]
        assert list(args[6 : 6 + len(expected_ext)]) == expected_ext
        assert args[-1] == b"{}"
