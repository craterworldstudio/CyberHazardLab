# Cyber Hazard Lab Documentation

Welcome to the technical documentation for **Cyber Hazard Lab (CHL)**.

Cyber Hazard Lab is a local cybersecurity and network simulation environment designed to model networking concepts, devices, services, telemetry, and security scenarios without interacting with a real network.

## Documentation map

- [Architecture](architecture/overview.md)
- [Networking](networking/ethernet.md)
- [Devices](devices/hosts.md)
- [Services](services/overview.md)
- [API](api/overview.md)
- [Frontend](frontend/overview.md)
- [Development](development/setup.md)
- [Security](security/isolation.md)

## Project philosophy

CHL treats the simulated network as a software-defined world. Devices, interfaces, frames, packets, protocols, services, and events are represented by Python objects and move through the simulation engine rather than through the host operating system's network stack.

The goal is educational fidelity rather than production networking performance.

## Source tree

The main implementation is divided broadly into:

- `backend/core/` — fundamental simulation objects.
- `backend/network/` — network protocols and forwarding behavior.
- `backend/services/` — simulated application services.
- `backend/state/` — simulation state management.
- `backend/orchestrator.py` — coordination of simulation behavior.
- `application/` — HTTP server, API routes, terminal integration, and frontend assets.

For implementation details, see the individual documents in this directory.
