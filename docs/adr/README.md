# Architecture Decision Records (ADR)

Architecture decisions for `redis_func_cache`, recorded as numbered,
immutable documents. When a decision is revised, a new ADR is written that
supersedes the old one — existing ADRs are never edited in place.

| #   | Decision                                                 | Status   | Date       |
| --- | -------------------------------------------------------- | -------- | ---------- |
| 1   | [Eviction Policy Roadmap Beyond LRU/LRU-T/LFU][adr-0001] | Accepted | 2026-09-29 |
| 2   | [Hyperbolic (LFU-with-aging) Eviction Policy][adr-0002]  | Accepted | 2026-09-29 |
| 3   | [GDSF Eviction Policy][adr-0003]                         | Accepted | 2026-09-29 |
| 4   | [Random Admission Policy][adr-0004]                      | Accepted | 2026-09-29 |

[adr-0001]: 0001-eviction-policy-roadmap.md
[adr-0002]: 0002-hyperbolic-eviction-policy.md
[adr-0003]: 0003-gdsf-eviction-policy.md
[adr-0004]: 0004-random-admission-policy.md
