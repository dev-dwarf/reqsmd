{
  "req": "REQSMD shall maintain bidirectional link tracking between requirements.",
  "priority": 1,
  "verified-hash": "09b0f001f1c416fd2dc0cdbd8fed809fbd61c844b84e12a905179649028f171f",
  "verified-by": "bob",
  "date_added": "2026-April-07",
}
---
When requirement `A` references requirement `B` using `[[B]]`, the system must track:
- `A` has a "link-to" relationship with `B`
- `B` has a "link-from" relationship with `A`

This enables traceability in both directions. See [[FMT-8]] for reference syntax.
