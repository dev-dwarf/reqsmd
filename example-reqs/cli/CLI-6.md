{
  "req": "The CLI shall provide a `reqsmd req verify REQ-ID USER` command to hash and record verification of a requirement.",
  "priority": 1,
  "verified-hash": "f024bd0b37d6b9b08c0afcb3ee0eb4bcbad9638701119fcb5fb7e8ebc5c9ef64",
  "verified-by": "bob",
}
---
The command writes `verified-hash` and `verified-by` fields directly into the requirement's frontmatter. These fields are stored in version control alongside the requirement content, making the verification history auditable via `git log`.

The `--force` flag recursively verifies any unverified dependencies before verifying the target, performing a topological traversal. Circular dependencies are detected and reported as errors. See [[VER-3]] for ordering constraints.
