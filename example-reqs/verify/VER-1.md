{
  "req": "MDOORS shall support requirement verification via cryptographic hashing.",
  "priority": 1,
  "phase": "core",
  "verified-hash": "0c3349300f29d7c436d7e25dbfda3f0c2cbe10ebb0cf695d0246d4987f46e5d6",
  "verified-by": "bob",
}
---
Verification allows teams to confirm that a requirement has been reviewed and approved in its current state. Once verified, any change to the requirement or its dependencies is detectable.

This provides a lightweight "compile step" for requirements: like a build system, it flags work that is out of date and must be reviewed before the project can be considered consistent.
