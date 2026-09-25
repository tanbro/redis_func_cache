"""One-off generator for ``tests/_golden.json``.

Run against any implementation to (re)freeze the observable contract of every
built-in policy:

- the Redis key pair produced by :meth:`calc_keys` for two distinct functions,
- the sub-key hash produced by :meth:`calc_hash` for fixed inputs,
- the extra ARGV entries from :meth:`calc_ext_args`,
- the (get, put) Lua script file names.

The committed JSON was generated from the pre-refactor (mixin-MRO)
implementation; after the composition refactor the same assertions must still
hold — see ``tests/test_golden.py``.

Usage::

    uv run python -m tests._gen_golden
"""

import json
from pathlib import Path

import redis_func_cache.policies.fifo as fifo_mod
import redis_func_cache.policies.lfu as lfu_mod
import redis_func_cache.policies.lru as lru_mod
import redis_func_cache.policies.mru as mru_mod
import redis_func_cache.policies.rr as rr_mod
from redis_func_cache.policies import Policy

from ._golden_fns import fn_a, fn_b

POLICY_MODULES = (fifo_mod, lfu_mod, lru_mod, mru_mod, rr_mod)
PREFIX, NAME = "gp:", "gn"
ARGS, KWDS = (1,), {"x": "a"}


def main() -> None:
    golden: dict[str, dict] = {}
    for module in POLICY_MODULES:
        for attr in dir(module):
            policy = getattr(module, attr)
            if not isinstance(policy, Policy):
                continue
            policy._bind(PREFIX, NAME)
            golden[attr] = {
                "keys_a": list(policy.calc_keys(fn_a, ARGS, KWDS)),
                "keys_b": list(policy.calc_keys(fn_b, ARGS, KWDS)),
                "hash": policy.calc_hash(fn_a, ARGS, KWDS).hex(),  # type: ignore[union-attr]
                "ext_args": list(policy.calc_ext_args(fn_a, ARGS, KWDS) or ()),
                "scripts": [policy.scripts.get_script, policy.scripts.put_script],
            }
    out = Path(__file__).with_name("_golden.json")
    out.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(golden)} policies to {out}")


if __name__ == "__main__":
    main()
