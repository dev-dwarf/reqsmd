{
  "req": "The search functionality shall use sql.js for client-side SQL queries.",
  "priority": 2,
  "phase": "web",
  "verified-hash": "79b3ac23ec0cb60bc26fe0f9ffb4e37ed807b49646dc8960757ab181ae2df00c",
  "verified-by": "alice",
}
---
sql.js provides:
- SQLite-compatible SQL in the browser via WebAssembly
- Fast query execution on the client
- No server-side infrastructure needed

Implements [[SRCH-1]].
