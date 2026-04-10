{
  "req": "Requirements within a document shall be ordered by their ID suffix.",
  "priority": 2,
  "phase": "core",
  "verified-hash": "488729088a0e855cffd6d3cd8e162318b47be584ebc9639e23868e46c1e287f9",
  "verified-by": "alice",
}
---
Sorting by the numeric suffix (e.g., `REQ-1`, `REQ-1.1`, `REQ-2`) ensures a consistent, predictable order:
- `REQ-1` comes before `REQ-1.1`
- `REQ-1.1` comes before `REQ-1.2`
- More dots indicate deeper nesting levels
