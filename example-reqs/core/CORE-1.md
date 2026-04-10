{
  "req": "MDOORS shall maintain bidirectional link tracking between requirements.",
  "priority": 1,
  "phase": "core",
  "verified-hash": "590f0ccfdc6bd7baee2f8d26d45eacc80afe74bb03d07053e22c8135239abca2",
  "verified-by": "alice",
}
---
When requirement `A` references requirement `B` using `[[B]]`, the system must track:
- `A` has a "link-to" relationship with `B`
- `B` has a "link-from" relationship with `A`

This enables traceability in both directions. See [[FMT-8]] for reference syntax.
