{
  "req": "The CLI shall provide a `reqsmd check` command to check all requirements in the project in a single pass.",
  "priority": 1,
  "phase": "cli",
  "verified-hash": "7f4c3d230a37ff054441c45a5495dc53a6f49a529a7ca030fe841240338dff2f",
  "verified-by": "bob",
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
