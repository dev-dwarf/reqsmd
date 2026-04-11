{
  "req": "The CLI shall provide a `reqsmd check` command to check all requirements in the project in a single pass.",
  "priority": 1,
  "phase": "cli",
  "verified-hash": "4049633eb7d1dc99dae442839f1e1ef0b8156e252e03127a919dd5cf3fc6e350",
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
