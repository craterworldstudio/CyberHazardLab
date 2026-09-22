# Simulation Engine

The simulation engine is the runtime world of Cyber Hazard Lab.

The central class is `Simulation` in:

```text
backend/orchestrator.py
```

`Simulation` composes the major backend subsystems and owns the lifecycle of simulated devices.

## Simulation object

At initialization, the simulation creates:

```python
self.network = Network(name)
self.dhcp = DHCP(self.network)

self.hosts = {}
self.switches = {}
self.routers = {}
```

It also maintains:

```python
self.is_running
self.settings
self.rename_map
```

The simulation therefore acts as the top-level runtime container.

---

## Device lifecycle

Devices are created through the simulation rather than directly by the frontend.

### Host

```text
Simulation.add_host()
        ↓
Host()
        ↓
Network.add_host()
        ↓
simulation.hosts[name]
```

### Router

```text
Simulation.add_router()
        ↓
Router()
        ↓
Network.add_host()
        ↓
simulation.routers[name]
```

### Switch

```text
Simulation.add_switch()
        ↓
Switch()
        ↓
simulation.switches[name]
```

Hosts and routers are also registered with `Network.hosts`; switches are maintained separately because their architecture differs from Layer-3 nodes.

---

## Device lookup

`Simulation.get_device()` searches all three device collections:

```text
hosts
switches
routers
```

This gives application managers a unified device lookup mechanism.

---

## Naming

Device names are treated as unique across the entire simulation.

Creating a device whose name already exists in another device collection raises an error.

Renaming is also centralized in `Simulation.rename_device()`.

The simulation maintains:

```python
rename_map
```

This is important because persisted topology layouts may refer to an older device name.

---

## Running state

The simulation tracks whether it is running through:

```python
is_running
```

NCM uses this state when restarting devices.

When the simulation is running, a restarted device receives:

```text
status = ONLINE
boot_time = current time
```

Otherwise it returns to:

```text
status = OFFLINE
boot_time = None
```

---

## Event handling

`Simulation` attaches a callback to the network:

```python
self.network.on_event = self._handle_network_event
```

Network events therefore have two effects:

1. they are stored by `Network`
2. they can trigger simulation-level handling

Currently, high-severity events can place an affected device into an `ERROR` state when the event metadata identifies that device.

---

## Protocol processing

The simulation itself does not implement every protocol.

Instead, it composes protocol implementations:

```text
Simulation
   ↓
Node
   ├── ARP
   ├── routing
   ├── ICMP
   ├── TCP
   ├── UDP
   └── services
```

Switches independently compose:

```text
Switch
 ├── SwitchPort
 ├── Link
 └── MAC table
```

---

## Tick/update model

Interfaces and switches process received-frame buffers through update methods.

For example:

```python
NetworkInterface.process_rx_buffer()
Switch.update()
```

This gives the simulation an explicit mechanism for processing queued frames rather than requiring every operation to happen immediately inside `send()`.

---

## Validation

The simulation exposes validation functionality through the application API.

Validation is intended to check and repair/normalize simulation relationships before state is persisted.

The important architectural point is that validation belongs to the simulation layer rather than the frontend.
