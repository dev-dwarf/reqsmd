{
  "req": "MDOORS shall maintain bidirectional link tracking between requirements.",
  "priority": 1,
  "verified-hash": "6bf7e223cead5ed45257a39f3a63f1ef9deef3dc6622a44d47b7497dbd48169a",
  "verified-by": "alice",
}
---
When requirement `A` references requirement `B` using `[[B]]`, the system must track:
- `A` has a "link-to" relationship with `B`
- `B` has a "link-from" relationship with `A`

This enables traceability in both directions. See [[FMT-8]] for reference syntax.
