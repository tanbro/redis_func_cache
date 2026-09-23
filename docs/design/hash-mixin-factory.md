---
status: accepted
---

# Proposal: A Factory for Hash Mixin Combinations

## Background

`src/redis_func_cache/mixins/hash.py` defines hash mixins as the cross product of
three axes:

- serializer: JSON or pickle
- algorithm: md5, sha1, sha256, sha512
- digest encoding: raw digest bytes, hex string, base64 (padding stripped)

That is 2 × 4 × 3 = **24 classes** (`JsonMd5HashMixin`, `PickleSha256HexHashMixin`,
...), each differing only in the three fields of its `__hash_config__`:

```python
class PickleSha256HexHashMixin(AbstractHashMixin):
    __hash_config__ = HashConfig(algorithm="sha256", serializer=pickle.dumps, decoder=_HEX_DIGEST_DECODER)
```

Every additional serializer or algorithm would multiply the class count again, along
with the doc tables, `__all__` lists, and tests. Meanwhile `HashConfig` is already a
fully open extension point — `algorithm` accepts any name `hashlib.new` supports, and
`serializer`/`decoder` are arbitrary callables. Users who want an unlisted combination
(e.g. msgpack + sha3_256 + base64) can define it in two lines today.

## Proposal

Add a factory that generates mixin classes on demand instead of enumerating the
matrix:

```python
MsgpackSha3B64 = make_hash_mixin("MsgpackSha3B64", HashConfig(algorithm="sha3_256", serializer=msgpack.packb))
```

The factory takes the class name, a fully-specified :class:`HashConfig`, and an
optional base class. It deliberately does **not** accept string shorthands such as
`serializer="json"` / `decoder="hex"`: `HashConfig` is already the public, documented
extension point whose value domain (arbitrary `hashlib` algorithms, arbitrary
callables, `use_bytecode`) the string enums could only ever under-approximate. Two
parallel half-open interfaces would force every advanced user back down to
`HashConfig` anyway; the audience for the shorthand does not exist, since users who
want a listed combination already have the 24 named classes.

- The 24 existing classes stay hand-written (not aliases) — explicit classes keep
  autodoc and `inheritance-diagram` working, and the boilerplate is stable.
- Each call returns a fresh class. Two calls with equal configurations produce
  classes that are not `isinstance`-compatible with each other; this is acceptable
  because mixins are composed once at definition time and type checks in practice
  target the stable `AbstractHashMixin` base. The factory does not memoize: caching
  would add module-level mutable state (and name-vs-config key ambiguity) to serve
  a usage pattern that does not occur.

## Non-goals

- No new combination classes for their own sake. The digest only addresses cache keys
  — it is not a security boundary — so md5/sha1/sha256/sha512 already over-cover the
  real demand; adding sha3/blake2 as classes would suggest a choice users do not need
  to make.
- No change to hash semantics: two mixins with the same `__hash_config__` produce the
  same hashes as today.

## Note on hash stability

Separately from this proposal: the default JSON hash serializer recently gained
`ensure_ascii=False` and compact separators, and any future change to serializer
output changes hash inputs, invalidating existing cache keys (one cold-start wave per
deployment). The factory should document that its output is stable only per library
version, and pin the standard serializer/decoder parts it references.
