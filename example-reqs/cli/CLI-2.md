{
  "req": "The CLI shall support adding new requirements via `reqsmd req add`.",
  "priority": 1,
  "phase": "core",
  "verified-hash": "b69bdaadda141239882f20e618890f3c94bed09d253694010b729c8bbea44923",
  "verified-by": "alice",
}
---
Adding requirements through the CLI ensures:
- Consistent file structure and formatting
- Automatic population of template fields (see [[FMT-9]])
- Correct placement in the document hierarchy

Usage: `reqsmd req add $REQID`
