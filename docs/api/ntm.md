# NTM API

NTM means **Network Topology Manager**.

It is responsible for topology-oriented operations and provides the frontend with a controlled interface for creating and manipulating simulated network topology.

## Role

NTM sits between topology UI actions and backend simulation objects.

```text
Topology UI
    ↓
NTM
    ↓
Simulation state
```

## Responsibilities

Typical NTM responsibilities include:

- device creation
- topology changes
- device lookup
- topology serialization
- connection management

## Source

The main application integration is under `application/ntm/ntm.py`.

NTM should not contain low-level TCP, ARP, or Ethernet logic.
