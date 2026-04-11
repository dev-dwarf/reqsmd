{
  "req": "Requirements within a document shall be ordered by their ID suffix.",
  "priority": 2,
  "verified-hash": "7797e7a26f5d21aad5d94469190005d6ee85848316abce0b40fdc83c3a39c59a",
  "verified-by": "alice",
}
---
Sorting by the numeric suffix (e.g., `REQ-1`, `REQ-1.1`, `REQ-2`) ensures a consistent, predictable order:
- `REQ-1` comes before `REQ-1.1`
- `REQ-1.1` comes before `REQ-1.2`
- More dots indicate deeper nesting levels
