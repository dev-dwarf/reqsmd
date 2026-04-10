{
  "req": "The search functionality shall use sql.js for client-side SQL queries.",
  "priority": 2,
  "phase": "web",
  "verified-hash": "e262de8af3ebefc7d4d6f4d0e0dc34b3fea6277accf9921cbc46bcbea7fbee3a",
  "verified-by": "alice",
}
---
sql.js provides:
- SQLite-compatible SQL in the browser via WebAssembly
- Fast query execution on the client
- No server-side infrastructure needed

Implements [[SRCH-1]].
