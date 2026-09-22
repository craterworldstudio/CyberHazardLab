# Simulation Engine

The simulation engine is the software-defined environment in which CHL's network exists.

It models entities rather than opening real sockets or transmitting real Ethernet frames.

## Simulation objects

A typical network scenario contains:

```text
Network
 ├── Device
 │    ├── Interface
 │    └── Services
 └── Links / forwarding relationships
```

Network activity then produces objects such as:

```text
Ethernet Frame
    ↓
IP Packet
    ↓
TCP/UDP Segment
    ↓
Application Protocol
```

Not every communication path contains every layer. ARP, for example, operates differently from TCP-based traffic.

## Orchestration

`backend/orchestrator.py` coordinates simulation activity and provides a place for higher-level interactions to be connected without putting all behavior into individual device classes.

## Events

Events provide telemetry about important changes and actions in the simulated world.

Examples used by the project include events corresponding to DHCP leases, service creation, ARP replies, received frames, and flooded frames.

The event system is also an architectural foundation for the future SOC/observer interface.

## Determinism

Simulation behavior should be as deterministic as practical. Randomness may be used for generated identifiers or scenario behavior, but protocol logic should remain understandable and reproducible.

## Educational fidelity

CHL does not attempt to reproduce every implementation detail of Linux, Cisco IOS, TCP/IP, or real Ethernet hardware.

Instead, it models the concepts necessary to make network behavior visible and interactive.
