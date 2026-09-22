# Architecture Overview

Cyber Hazard Lab is divided into a simulation backend and a browser-based application layer.

```text
Browser
  │
  ├── Topology UI
  ├── NCM UI
  └── Terminal UI
       │
       ▼
application/
  │
  ├── HTTP/API routing
  ├── NTM integration
  ├── NCM integration
  └── terminal communication
       │
       ▼
backend/
  │
  ├── Core simulation objects
  ├── Network protocols
  ├── Services
  ├── State
  └── Orchestration
```

## Core principle

The browser is a control and visualization surface. It should not become the source of truth for simulation state.

The backend owns simulated devices, interfaces, network behavior, services, and events. The frontend requests state and sends actions through the application API.

## Major layers

### Core

`backend/core/` contains reusable primitives such as nodes, devices, hosts, interfaces, MAC addresses, events, and service metadata.

### Network

`backend/network/` implements simulated networking behavior including Ethernet frames, ARP, IP packets, routing, switching, TCP, UDP, DHCP, and related forwarding behavior.

### Services

`backend/services/` contains simulated application-layer daemons such as HTTP, DNS, DHCP, SSH, and Echo.

### State

`backend/state/` provides centralized handling of simulation state and persistence-related concerns.

### Application

`application/` exposes the simulation to the browser and provides UI-specific functionality such as NTM and NCM.

## Design boundary

A useful rule is:

> If something represents the simulated world, it belongs in the backend. If something only presents or controls that world, it belongs in the application layer.

This boundary prevents UI code from becoming tightly coupled to protocol implementation.
