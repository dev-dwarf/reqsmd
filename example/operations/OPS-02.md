{
  "priority": 1,
  "phase": "all",
}
---
# Fault Protection

The spacecraft shall implement **autonomous fault protection** to maintain safe configuration during communication gaps.

## Fault Responses

| Fault Type | Response |
|------------|----------|
| Attitude loss | Sun acquisition mode |
| Command loss | Use stored sequence |
| Power anomaly | Load shedding [[PWR-02]] |
| Receiver failure | Switch to backup |

*Critical for extended mission* where light-time delay exceeds 20 hours - ground intervention too slow for real-time response.
