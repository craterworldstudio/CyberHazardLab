# Architecture Overview

Cyber Hazard Lab is a Python-based network simulation environment with a browser interface. The important distinction is that the browser is **not the simulation**. The simulation exists in the backend, while `application/` provides the HTTP interface and visualization used to control it.

At runtime, the major relationship is:

```text
Browser
   │
   │ HTTP / JSON
   ▼
application/
   ├── API
   ├── NTM
   ├── NCM
   └── Terminal
   │
   ▼
backend/orchestrator.py
   │
   ▼
Simulation
   │
   ├── Hosts
   ├── Switches
   ├── Routers
   ├── Network
   ├── DHCP manager
   └── Global simulation settings
        │
        ├── Node
        │    ├── Interfaces
        │    ├── ARP
        │    ├── Routes
        │    ├── TCP connections
        │    ├── UDP connections
        │    └── Services / daemons
        │
        ├── Switch
        │    ├── Ports
        │    └── MAC table
        │
        └── Network
             ├── Links
             ├── Subnets
             └── Events
```

## The actual architectural layers

### 1. Simulation orchestration

`backend/orchestrator.py` contains the `Simulation` class.

`Simulation` owns the major collections of simulated devices:

```python
self.hosts
self.switches
self.routers
```

It also owns the simulated `Network` and DHCP manager:

```python
self.network = Network(name)
self.dhcp = DHCP(self.network)
```

The orchestrator is responsible for high-level lifecycle operations such as:

* creating hosts
* creating routers
* creating switches
* removing devices
* renaming devices
* creating interfaces
* connecting devices
* disconnecting devices
* adding/removing services
* starting/stopping services
* running/stopping the simulation
* validation
* simulation-wide settings

It is therefore the main composition layer of CHL.

---

## 2. Core simulation objects

The core classes live primarily in `backend/core/`.

### `Node`

`backend/core/node.py` is one of the most important classes in the project.

`Node` is the common Layer-3 implementation used by hosts and routers.

It owns:

* interfaces
* routes
* services
* ARP state
* TCP connections
* UDP connections
* service daemons
* device status
* default gateway
* packet transmission and reception

A `Node` therefore acts as the bridge between the lower-level network objects and higher-level services.

### `Host`

`backend/core/host.py` derives from `Node`.

A host:

* disables IP forwarding
* receives a default `eth0`
* receives a generated MAC address
* starts with `0.0.0.0`
* can contain services

Hosts represent endpoint systems such as PCs and servers.

### `Router`

`backend/network/router.py` also derives from `Node`.

A router differs primarily by enabling forwarding:

```python
self.forwarding_enabled = True
```

The same Layer-3 machinery in `Node` is therefore reused for routing rather than creating an entirely separate packet-processing implementation.

### `Switch`

`backend/network/switch.py` is separate from `Node`.

A switch operates around Ethernet frames and switch ports rather than the Layer-3 node implementation.

It maintains:

```python
self.ports
self.mac_table
```

---

## 3. The simulated network

`backend/network/network.py` contains the `Network` object.

The network maintains:

* hosts
* links
* subnets
* events
* network-level ARP state
* a reference to the simulation orchestrator

It also provides higher-level helpers for:

* locating hosts/devices
* route lookup
* service lookup
* service creation
* service startup/shutdown
* event recording

The network therefore acts as both a simulation-world container and an integration point for network-wide behavior.

---

## 4. Packet processing

Packets do not use Python's real networking stack.

Instead, CHL creates Python objects representing simulated network traffic.

For example:

```text
Packet
 ├── source_ip
 ├── destination_ip
 ├── protocol
 ├── payload
 └── ttl
```

The payload may itself contain:

```text
TCPPacket
UDPPacket
ICMPPacket
ARPPacket
```

Ethernet adds another layer:

```text
EthernetFrame
 ├── source_mac
 ├── destination_mac
 └── payload
```

A simplified transmission path is:

```text
Application service
       ↓
TCP / UDP
       ↓
IP Packet
       ↓
ARP resolution
       ↓
Ethernet Frame
       ↓
Interface
       ↓
Link
       ↓
Interface / SwitchPort
       ↓
Destination Node
```

The exact path depends on the protocol and topology.

---

## 5. Application services

Services have two distinct representations.

### Service model

`backend/core/service.py` defines the `Service` dataclass.

It stores:

* name
* protocol
* port
* status
* configuration
* enabled state

The service model does not contain the actual HTTP/DNS/SSH protocol implementation.

### Service daemon

`backend/services/base.py` defines `ServiceDaemon`.

Concrete daemons implement application behavior.

Examples:

```text
HTTPServerDaemon
DNSServerDaemon
SSHServerDaemon
SSHClientDaemon
DHCPServerDaemon
DHCPClientDaemon
DHCPRelayDaemon
EchoServerDaemon
```

`Node.get_service_daemon()` connects a service model to the appropriate daemon implementation.

This separation is important:

```text
Service
  = what is configured/running

ServiceDaemon
  = what the service actually does
```

---

## 6. Event system

`backend/core/event.py` defines the event structure.

An event contains:

```text
type
source
destination
protocol
port
severity
timestamp
metadata
```

`Network.add_event()` stores events and invokes the simulation's event callback.

The simulation callback currently uses high-severity events to update affected device status.

The event stream is also the foundation for future telemetry/SOC functionality.

---

## 7. Application layer

`application/` sits above the simulation.

It contains:

```text
application/
├── api.py
├── main.py
├── term_coms.py
├── ncm/
└── ntm/
```

The API translates HTTP requests into calls to NTM, NCM, and the simulation.

The browser therefore does not directly manipulate Python objects.

---

## 8. NTM and NCM

### NTM

`application/ntm/ntm.py` implements `NetworkTopologyManager`.

NTM handles topology-level operations:

* listing devices
* creating devices
* deleting devices
* renaming devices
* connecting devices
* disconnecting devices
* retrieving links
* retrieving device connections

### NCM

`application/ncm/ncm.py` implements `NetworkConfigurationManager`.

NCM handles device-level management:

* health
* restart
* interfaces
* interface configuration
* services
* service lifecycle
* device lookup
* renaming

The distinction is therefore:

```text
NTM
→ What devices and connections exist?

NCM
→ How is an existing device configured?
```

---

## 9. Persistence

`backend/state/manager.py` implements `StateManager`.

The state manager serializes simulation state into JSON.

Persisted information includes:

* devices
* links
* interfaces
* subnets
* routes
* MAC tables
* ARP caches
* services
* topology layout
* device rename mappings

The state file also has a version field:

```json
{
    "version": 1
}
```

This gives the persistence system a basis for future schema migration.

---

## 10. Frontend

The frontend is implemented with browser-native JavaScript.

Important modules include:

```text
application/static/js/
├── api.js
├── lab_app.js
├── ncm_app.js
├── topology.js
└── wel_app.js
```

The topology UI creates visual devices while the backend creates the authoritative simulated device.

For example:

```text
Palette drag
    ↓
JavaScript createDevice()
    ↓
POST /api/ntm/devices
    ↓
Simulation.add_host/add_switch/add_router
    ↓
Backend device exists
    ↓
Frontend renders returned device
```

This distinction is critical when debugging topology problems.

---

## 11. Architectural boundary

The intended dependency direction is:

```text
Frontend
   ↓
Application managers / API
   ↓
Simulation orchestration
   ↓
Core + network + services
```

Lower layers should not depend on the browser.

For example:

* TCP should not know that NCM exists.
* ARP should not know how a topology node is rendered.
* HTTP should not manipulate DOM elements.
* The frontend should not implement routing logic.

This keeps the simulation usable independently of its current browser interface.
