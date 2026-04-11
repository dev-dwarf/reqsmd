{
  "req": "Verification shall require all linked-to requirements to be verified before the dependent requirement can be verified.",
  "priority": 1,
  "verified-hash": "4362eb62eaefd4e61c3590a85a60c94d7abf49388e38623728df8a52ad9aed40",
  "verified-by": "bob",
  "date_added": "2026-April-10",
}
---
This ordering constraint ensures that each requirement's hash is computed against stable dependency hashes. If a dependency has not been verified, its hash contribution would be empty, producing an unstable hash that would fail check as soon as the dependency is later verified.

The `--force` flag on `reqsmd req verify` bypasses this check by recursively verifying unverified dependencies first.
