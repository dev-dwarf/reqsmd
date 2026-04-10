{
  "req": "The root folder shall contain a req-template.json file defining default fields.",
  "priority": 2,
  "phase": "core",
  "verified-hash": "1d2cb9c9e96a77fd8ec6632c30aaf1ddf99ed97ebe9ddec62ed48e3ccda9d184",
  "verified-by": "alice",
}
---
A template file ensures consistency across requirements in a project. It defines:
- Which metadata fields are available
- Default values for new requirements
- Which fields should be hidden in output

This supports the CLI requirement [[CLI-1]].
