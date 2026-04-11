{
  "req": "The verification hash shall cover the req field, any hash-include template fields, and the stored verification hashes of all linked-to requirements.",
  "priority": 1,
  "verified-hash": "5917f560a2c16d77c588dec179284a288528f9ee8f1d21405900109fcde22a40",
  "verified-by": "bob",
  "date_added": "2026-April-10",
}
---
Including the stored hashes of dependencies means that re-verifying a dependency invalidates all requirements that depend on it. This propagates changes up the traceability chain automatically.

The hash is computed as a SHA-256 digest of a canonical string:

```
req:<value>
<field>:<value>   (for each hash-include field, sorted)
dep:<id>:<hash>   (for each link_to, sorted by id)
```

The `hash-include` flag is configured per-field in `req-template.json`. See [[VER-1]].
