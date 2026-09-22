# Persistence

Persistence stores the simulated laboratory state so that a scenario can survive beyond a single process lifetime.

## Runtime versus persistent state

Runtime state includes transient protocol information such as active TCP connections.

Persistent state is more appropriate for:

- topology
- device configuration
- service configuration
- user-created scenarios

## Serialization

Persisted state should use explicit schemas rather than serializing arbitrary Python objects.

This reduces coupling between the storage format and implementation details.

## Future

A mature persistence layer could support:

- scenario files
- save/load
- autosave
- versioned schemas
- migration of older scenarios
- shareable laboratory configurations
