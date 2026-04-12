{
  "req": "The CLI shall provide a `reqsmd check` command to check all requirements in the project in a single pass.",
  "priority": 1,
  "verified-hash": "8b0be963088bbf81c935e2b2970f0f6d660e98ec68a4732766d942f96f4958c8",
  "verified-by": "bob",
  "date_added": "2026-April-07",
}
---
The command checks all requirements efficiently by building a single snapshot of stored dependency hashes, then computing each requirement's current hash against that snapshot. This is O(n) in the number of requirements.

Output lists one line per failing requirement, then exits non-zero if any fail:

```
UNVERIFIED VER-1
FAIL CORE-3
```

Or on success:

```
OK (41 requirements verified)
```

Intended for use in CI pipelines as a gating check. See [[CLI-7]].
