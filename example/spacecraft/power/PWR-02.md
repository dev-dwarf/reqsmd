{
  "priority": 2,
  "phase": "extended",
}
---
# Power Management - Extended Mission

As RTG power decreases, the spacecraft shall implement **load shedding** to maintain critical functions.

## Priority Order

1. **Critical**: Communications [[COMM-01]], computer [[COMP-01]]
2. **High**: Fields instruments [[FLD-01]]
3. **Medium**: Plasma science
4. **Low**: Imaging (disabled post-Neptune)

Heater management is critical - instruments may be permanently disabled to save power for [[MISS-02]].
