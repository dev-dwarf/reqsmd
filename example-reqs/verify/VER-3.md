{
  "req": "Verification shall require all linked-to requirements to be verified before the dependent requirement can be verified.",
  "priority": 1,
  "phase": "core",
  "verified-hash": "f1fae65df0ec90d65e6e28279030a403d1867bee56f4fe7be54233fe92cfd46f",
  "verified-by": "bob",
}
---
This ordering constraint ensures that each requirement's hash is computed against stable dependency hashes. If a dependency has not been verified, its hash contribution would be empty, producing an unstable hash that would fail check as soon as the dependency is later verified.

The `--force` flag on `reqsmd req verify` bypasses this check by recursively verifying unverified dependencies first.
