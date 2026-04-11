{
  "req": "The verification hash shall cover the req field, any hash-include template fields, and the stored verification hashes of all linked-to requirements.",
  "priority": 1,
  "phase": "core",
  "verified-hash": "edac473d4ef4566f3c228cded0273116c358760d19a44b7ad79cabd5290d3016",
  "verified-by": "bob",
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
