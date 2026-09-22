# Interfaces

Interfaces connect devices to the simulated network.

An interface may have:

- name
- MAC address
- IP configuration
- link state
- parent device
- protocol-related state

## Layer boundary

The interface is the natural boundary between a device and the simulated link.

```text
Device
  │
Interface
  │
Link
  │
Interface
  │
Device
```

## Management

NCM exposes interface information so users can inspect device connectivity without directly accessing Python objects.
