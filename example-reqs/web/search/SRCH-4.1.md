{
  "req": "The sql.js library shall be vendored locally rather than loaded from a CDN.",
  "priority": 2,
  "phase": "web",
  "verified-hash": "5deff7f3cb5e27f908c768a6b6eed780b6e6b6198e21ff935d2d5efbb85fa42f",
  "verified-by": "alice",
}
---
Vendoring dependencies:
- Enables offline use of the website
- Removes external network dependencies
- Ensures consistent behavior regardless of CDN availability

The `sql-wasm.js` and `sql-wasm.wasm` files should be included in the generated output.
