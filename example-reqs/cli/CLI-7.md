{
  "req": "The CLI shall provide a `reqsmd req check REQ-ID` command to verify a single requirement against its stored hash.",
  "priority": 1,
  "verified-by": "bob",
  "verified-hash": "80a7e6c26ace9746f57662810e69d6da82b62dfb672cb66f8ca0098e25b6890d",
  "date_added": "2026-April-10",
}
---
Outputs one of:

- `OK REQ-ID` — hash matches, requirement unchanged since verification
- `FAIL REQ-ID` — hash mismatch, requirement or a dependency has changed
- `UNVERIFIED REQ-ID` — no stored hash, requirement has never been verified

Exits non-zero on FAIL or UNVERIFIED. See [[VER-2]] for hash computation.
