"""Fixed functions shared by the golden-fixture generator and the golden tests.

The policies' key names (multiple/cluster-multiple variants) and hashes embed
the function's qualified name and bytecode, so both sides must hash exactly
the same function objects from this module.
"""


def fn_a(x):
    return x


def fn_b(x):
    return x * 2
