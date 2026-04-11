{
  "req": "The CLI shall provide a `reqsmd req check REQ-ID` command to verify a single requirement against its stored hash.",
  "priority": 1,
  "phase": "cli",
  "verified-by": "bob",
  "verified-hash": "47abf6bc74fd0b1e85264fb909424bc8dcb2a5e3c13ea79753ddf7e63fcba9ba",
}
---
Outputs one of:

- `OK REQ-ID` — hash matches, requirement unchanged since verification
- `FAIL REQ-ID` — hash mismatch, requirement or a dependency has changed
- `UNVERIFIED REQ-ID` — no stored hash, requirement has never been verified

Exits non-zero on FAIL or UNVERIFIED. See [[VER-2]] for hash computation.
