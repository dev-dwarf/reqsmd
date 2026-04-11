{
  "req": "The CLI shall provide a `reqsmd req verify REQ-ID USER` command to hash and record verification of a requirement.",
  "priority": 1,
  "phase": "cli",
  "verified-hash": "035f6c0f37605d04854d17413f719e996ed41cd35535cdab732c70adc443b20a",
  "verified-by": "bob",
}
---
The command writes `verified-hash` and `verified-by` fields directly into the requirement's frontmatter. These fields are stored in version control alongside the requirement content, making the verification history auditable via `git log`.

The `--force` flag recursively verifies any unverified dependencies before verifying the target, performing a topological traversal. Circular dependencies are detected and reported as errors. See [[VER-3]] for ordering constraints.
