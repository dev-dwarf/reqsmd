{
  "req": "MDOORS shall support requirement verification via cryptographic hashing.",
  "priority": 1,
  "phase": "core",
  "verified-hash": "4c0f12ddc0662917152b5d8cdb55f53bc8f3f71e97af8992bbdb84a95263e030",
  "verified-by": "bob",
}
---
Verification allows teams to confirm that a requirement has been reviewed and approved in its current state. Once verified, any change to the requirement or its dependencies is detectable.

This provides a lightweight "compile step" for requirements: like a build system, it flags work that is out of date and must be reviewed before the project can be considered consistent.
