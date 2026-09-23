# State Management

Simulation state must have a single authoritative owner.

CHL uses `backend/state/manager.py` for centralized state-related responsibilities.

## Why centralized state matters

Without centralized state, the following problems become likely:

- frontend and backend disagree about topology
- multiple objects represent the same device
- stale service information is displayed
- restarts leave behind stale references
- persistence becomes difficult

## State categories

Important state includes:

- devices
- interfaces
- addresses
- links
- services
- protocol tables
- event history
- configuration

## Persistence

Persistence is intentionally treated separately from runtime simulation behavior.

See [Persistence](../development/persistence.md).

## State mutation

Prefer explicit backend operations over arbitrary mutation from the frontend.

For example:

```text
UI request
  → API operation
    → backend mutation
      → event
        → updated state
```

This gives the system a clear audit trail and makes future SOC functionality easier to implement.
