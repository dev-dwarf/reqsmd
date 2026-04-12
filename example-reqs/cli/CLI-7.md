{
  "req": "The CLI shall provide a `reqsmd req check REQ-ID` command to verify a single requirement against its stored hash.",
  "priority": 1,
  "verified-by": "bob",
  "verified-hash": "c4484f6e20919a091b669e4a59fbc15e1894a94c52d3d754e6a373af04b13782",
  "date_added": "2026-April-10",
}
---
Outputs one of:

- `OK REQ-ID` — hash matches, requirement unchanged since verification
- `FAIL REQ-ID` — hash mismatch, requirement or a dependency has changed
- `UNVERIFIED REQ-ID` — no stored hash, requirement has never been verified

Exits non-zero on FAIL or UNVERIFIED. See [[VER-2]] for hash computation.
