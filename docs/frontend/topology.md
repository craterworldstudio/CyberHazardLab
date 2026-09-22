# Topology Frontend

The topology interface is the visual representation of the simulated network.

## Responsibilities

It should allow the user to:

- view devices
- create devices through NTM
- inspect topology
- create or manipulate connections
- open management interfaces

## NTM relationship

Topology editing is a frontend representation of NTM operations.

```text
User action
   ↓
Topology UI
   ↓
NTM API
   ↓
Backend topology
```

## Future

Potential improvements include:

- live packet visualization
- link-state indicators
- VLAN visualization
- traffic animation
- topology validation
