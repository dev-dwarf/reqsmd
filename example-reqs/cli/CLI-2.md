{
  "req": "The CLI shall support adding new requirements via `reqsmd req add`.",
  "priority": 1,
  "phase": "core",
}
---
Adding requirements through the CLI ensures:
- Consistent file structure and formatting
- Automatic population of template fields (see [[FMT-9]])
- Correct placement in the document hierarchy

Usage: `reqsmd req add $REQID`
