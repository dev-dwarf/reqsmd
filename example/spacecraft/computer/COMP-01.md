{
  "priority": 1,
  "phase": "all",
}
---
# Flight Computer System

The spacecraft shall employ **redundant flight computers** for command processing, attitude control, and data handling.

## Architecture

```
CCS (Computer Command Subsystem)
  ├── Primary processor
  ├── Backup processor
  └── 69.63 KB memory

AACS (Attitude and Articulation Control)
  └── Dedicated processor
```

Radiation hardened per [[SC-02]]. Controls all spacecraft functions including [[SC-03]].
