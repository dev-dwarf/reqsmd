{
  "req": "The sql.js library shall be vendored locally rather than loaded from a CDN.",
  "priority": 2,
  "verified-hash": "962edcdbf00e13d8c8be093bbb5b967893800800ba19aefeba35e81e82f78934",
  "verified-by": "alice",
  "date_added": "2026-April-07",
}
---
Vendoring dependencies:
- Enables offline use of the website
- Removes external network dependencies
- Ensures consistent behavior regardless of CDN availability

The `sql-wasm.js` and `sql-wasm.wasm` files should be included in the generated output.
