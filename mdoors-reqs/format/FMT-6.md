{
  "req": "Requirements within a document shall be ordered by their ID suffix.",
  "priority": 2,
  "phase": "core",
}
---
Sorting by the numeric suffix (e.g., `REQ-1`, `REQ-1.1`, `REQ-2`) ensures a consistent, predictable order:
- `REQ-1` comes before `REQ-1.1`
- `REQ-1.1` comes before `REQ-1.2`
- More dots indicate deeper nesting levels
