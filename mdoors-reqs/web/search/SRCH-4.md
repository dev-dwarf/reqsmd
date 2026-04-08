{
  "req": "The search functionality shall use sql.js for client-side SQL queries.",
  "priority": 2,
  "phase": "web",
}
---
sql.js provides:
- SQLite-compatible SQL in the browser via WebAssembly
- Fast query execution on the client
- No server-side infrastructure needed

Implements [[SRCH-3]] and [[SRCH-1]].
