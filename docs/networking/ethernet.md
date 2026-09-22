# Ethernet

Ethernet is the link-layer transport mechanism used by Cyber Hazard Lab.

CHL does not create real Ethernet frames or access a physical network interface. Instead, Ethernet is represented entirely by Python objects and simulated links.

The primary implementation is:

```text
backend/network/frame.py
backend/network/link.py
backend/core/interface.py
backend/network/switchport.py
````

## EthernetFrame

The fundamental frame object is:

```python
@dataclass
class EthernetFrame:
    source_mac: str
    destination_mac: str
    payload: Packet
```

A frame therefore contains three pieces of information:

* source MAC address
* destination MAC address
* payload

The payload is normally another simulated protocol object.

For example:

```text
EthernetFrame
├── source_mac
├── destination_mac
└── payload
      └── Packet
           └── TCPPacket / UDPPacket / ICMPPacket
```

ARP is also transported through an Ethernet frame, but its payload is an `ARPPacket` rather than an IP `Packet`.

---

## Links

`backend/network/link.py` contains the `Link` class.

A link represents a direct connection between exactly two endpoints:

```text
Endpoint A
    │
  Link
    │
Endpoint B
```

The endpoints may be:

* network interfaces
* switch ports

`Link.transmit()` determines the endpoint opposite the sender and calls that endpoint's `receive()` method.

Conceptually:

```python
receiver = link.other_end(sender)
receiver.receive(frame)
```

There is therefore no global Ethernet medium simulation.

A frame travels from one endpoint to the other through the `Link` object.

---

## Interfaces

A network interface owns the connection between a node and a link.

When an interface sends a frame, it ultimately passes the frame into its attached link.

The link then delivers the frame to the other endpoint.

This gives CHL the following physical topology abstraction:

```text
Node
 │
NetworkInterface
 │
Link
 │
NetworkInterface / SwitchPort
 │
Node / Switch
```

---

## Switches

A switch does not directly receive frames from the link into its forwarding logic.

`SwitchPort.receive()` places the frame into the port's receive buffer:

```python
self.rx_buffer.append(frame)
```

The switch later processes that buffer through:

```python
SwitchPort.process_rx_buffer()
```

which calls:

```python
self.switch.receive(frame, self.port_number)
```

This makes the switch's forwarding step explicit rather than recursively forwarding the frame immediately from the link.

---

## Broadcast Ethernet

The simulator uses:

```text
FF:FF:FF:FF:FF:FF
```

as the Ethernet broadcast address.

Switches recognize this destination and transmit the frame through every connected port except the incoming port.

A `FRAME_BROADCAST` event is generated.

ARP requests and other broadcast traffic can therefore propagate through the simulated switching topology.

---

## Ethernet events

Switch forwarding generates events such as:

```text
FRAME_RECEIVED
FRAME_BROADCAST
FRAME_FLOODED
FRAME_FORWARDED
FRAME_DROPPED
```

These events are recorded by the network event system and form an important part of CHL's observability.

---

## Important limitation

This is a conceptual Ethernet implementation, not a bit-level Ethernet implementation.

CHL currently does not model things such as:

* Ethernet preambles
* FCS
* collision detection
* physical signaling
* frame-size enforcement
* real NIC hardware
* real Ethernet drivers

The goal is to model addressing and forwarding behavior needed by the network simulator.

````

---

## `docs/networking/arp.md`
## `docs/networking/ip.md`

```md
# IP

CHL's IP layer is represented by the `Packet` class in:

```text
backend/network/packet.py
````

The IP layer is processed primarily by `Node` in:

```text
backend/core/node.py
```

## Packet representation

The base packet contains:

```python
@dataclass
class Packet:
    source_ip: str
    destination_ip: str
    protocol: str
    payload: Any = None
    ttl: int = 64
    metadata: dict[str, Any] = ...
```

Therefore an IP packet in CHL contains:

* source IP
* destination IP
* protocol
* payload
* TTL
* optional metadata

---

## TTL

Packets start with:

```text
TTL = 64
```

The implementation validates that TTL is an integer and is not negative.

TTL exists so that routing behavior can eventually model packet lifetime and routing loops.

The packet model therefore already has the field necessary for TTL-aware forwarding.

---

## Receiving an IP packet

A node receives an Ethernet frame first.

If the frame contains an IP `Packet`, the node passes it into its IP-processing path.

The node then determines whether the destination belongs to the node.

Conceptually:

```text
Ethernet frame
      ↓
destination MAC accepted
      ↓
Packet
      ↓
destination IP
      ├── local
      ├── broadcast
      └── remote
```

---

## Local delivery

For a packet destined to the node itself, the protocol field determines the next handler.

CHL currently dispatches transport/control traffic such as:

```text
ICMP
TCP
UDP
```

to their respective subsystems.

---

## Forwarding

If the packet is not local, forwarding depends on the node's forwarding state.

Routers enable forwarding.

Hosts do not.

The router then performs a route lookup and determines an outgoing interface.

---

## Connected routes

When an interface receives an IP/subnet configuration, the node can install a connected route through its interface.

This allows a node to recognize destinations belonging directly to one of its connected networks.

The routing layer can therefore distinguish:

```text
directly connected network
```

from:

```text
network requiring a next hop
```

---

## IP and ARP

IP and ARP are tightly connected in the simulator.

IP decides:

```text
Where should this packet go?
```

ARP determines:

```text
What MAC address should receive it on this Ethernet segment?
```

The resulting path is:

```text
Destination IP
      ↓
Route lookup
      ↓
Outgoing interface / next hop
      ↓
ARP resolution
      ↓
Destination MAC
      ↓
Ethernet frame
```

---

## IP is not real networking

CHL does not construct Linux kernel IP packets or use the host's routing table.

All IP behavior remains inside the Python simulation.

````

---

## `docs/networking/routing.md`

```md
# Routing

Routing is implemented primarily by `Node` and `Router`.

Relevant files:

```text
backend/core/node.py
backend/network/router.py
backend/network/network.py
````

## Router model

`Router` inherits from `Node`.

This is an important architectural decision:

```text
Router
  ↓
Node
```

A router therefore reuses the same packet-processing infrastructure as a host.

The key difference is:

```python
self.forwarding_enabled = True
```

Hosts do not enable IP forwarding by default.

---

## Route representation

A route contains information such as:

```text
destination
interface
next_hop
```

The node maintains a routing table and provides route lookup functionality.

---

## Longest-prefix matching

Route selection uses the most specific matching network.

For example, conceptually:

```text
10.0.0.0/8
10.1.0.0/16
10.1.5.0/24
```

A destination of:

```text
10.1.5.42
```

should prefer the `/24` route.

This is implemented through IP-network containment and route selection in the node.

---

## Connected routes

Interfaces can contribute connected routes.

If an interface has:

```text
IP:     10.0.0.1
Subnet: 10.0.0.0/24
```

the node can recognize:

```text
10.0.0.0/24
```

as directly reachable through that interface.

`Network.get_route()` also checks interface subnets when resolving a destination.

---

## Forwarding flow

A routed packet follows approximately:

```text
Incoming Ethernet frame
        ↓
Node receives Packet
        ↓
Is destination local?
        │
        └── no
             ↓
        forwarding enabled?
             │
             └── yes
                  ↓
             route lookup
                  ↓
             outgoing interface
                  ↓
             next-hop IP
                  ↓
             ARP resolution
                  ↓
             Ethernet transmission
```

---

## Default gateway

Routers expose:

```python
default_gateway
```

and hosts may have a default gateway associated with their configuration.

A default route provides a path for destinations not matched by a more specific route.

---

## Router interfaces

`Router.__getattr__()` provides lazy creation of Ethernet interfaces when an `eth*` attribute is requested.

For example, requesting:

```python
router.eth0
```

can create a `NetworkInterface` if it does not already exist.

The generated interface starts with:

```text
IP:     0.0.0.0
Subnet: 0.0.0.0/0
```

and receives a generated MAC address.

---

## Current limitations

The routing implementation does not currently attempt to emulate a complete enterprise routing stack.

There is no full implementation of:

* OSPF
* BGP
* RIP
* route redistribution
* administrative distance
* ECMP
* policy-based routing

These are possible future simulation features.

````

---

## `docs/networking/switching.md`

```md
# Switching

Switching is implemented in:

```text
backend/network/switch.py
backend/network/switchport.py
````

The CHL switch is an Ethernet forwarding device with a simulated MAC address table.

## Switch structure

A switch contains:

```python
self.ports = {}
self.mac_table = {}
```

Each port is a `SwitchPort`.

A port contains:

* switch reference
* port number
* link
* mode
* receive buffer

---

## Frame reception

Frames arriving at a switch port are first buffered:

```python
SwitchPort.receive(frame)
```

The frame is appended to:

```python
rx_buffer
```

The switch later processes it through:

```python
Switch.update()
```

which asks each port to process its receive buffer.

This produces:

```text
Link
 ↓
SwitchPort.receive()
 ↓
rx_buffer
 ↓
SwitchPort.process_rx_buffer()
 ↓
Switch.receive()
```

---

## MAC learning

When a switch receives a frame, it can learn the source MAC address.

The table is represented as:

```text
MAC address → switch port
```

For example:

```text
AA:BB:CC:DD:EE:01 → Port 1
AA:BB:CC:DD:EE:02 → Port 3
```

The switch's `auto_mac_learning` setting controls whether learning occurs.

The value can be:

```text
True
False
"inherit"
```

When set to `"inherit"`, the switch can use the global simulation setting:

```text
settings["auto_mac_learning"]
```

---

## Known unicast

If the destination MAC exists in the MAC table, the switch forwards the frame to the learned port.

Example:

```text
Incoming: Port 1
Destination MAC: MAC-B

MAC table:
MAC-B → Port 3

Result:
Port 3
```

The switch generates:

```text
FRAME_FORWARDED
```

---

## Unknown unicast

If the destination MAC is not present in the table, the switch floods the frame to all connected ports except the incoming port.

The switch generates:

```text
FRAME_FLOODED
```

This models normal unknown-unicast flooding.

---

## Broadcast

A destination MAC of:

```text
FF:FF:FF:FF:FF:FF
```

causes a broadcast.

The switch sends the frame to every connected port except the incoming port.

The corresponding event is:

```text
FRAME_BROADCAST
```

---

## Source-port destination

If the MAC table says that the destination exists on the same port from which the frame arrived, the switch drops the frame.

The event is:

```text
FRAME_DROPPED
```

with:

```text
reason = DESTINATION_ON_SOURCE_PORT
```

---

## Switch-to-switch links

`Switch.connect_switch()` creates two trunk-mode ports:

```text
Switch A
  │
trunk port
  │
 Link
  │
trunk port
  │
Switch B
```

The current implementation does not yet implement VLAN tagging or trunk VLAN filtering.

The `mode="trunk"` value therefore represents topology/configuration state rather than a complete IEEE 802.1Q implementation.

---

## Router connections

`Switch.connect_router()` creates a trunk-mode switch port and connects it to a router interface.

This allows the simulated topology to represent:

```text
Host
 ↓
Switch
 ↓
Router
 ↓
another network
```

---

## MAC aging

The switch exposes:

```python
mac_aging_time = 300
```

However, the current forwarding implementation does not perform a complete periodic MAC-aging process.

The field therefore represents configuration intended for future/extended behavior rather than a fully implemented aging engine.

---

## Future switching features

Potential extensions include:

* VLANs
* 802.1Q tagging
* trunk VLAN filtering
* STP
* MAC aging
* port security
* storm control
* link-state failures

````

---

## `docs/networking/icmp.md`

```md
# ICMP

ICMP is represented by `ICMPPacket` in:

```text
backend/network/packet.py
````

and is handled by the node's packet-processing logic.

## Packet representation

An ICMP packet contains:

```python
@dataclass
class ICMPPacket:
    type: str
    code: int = 0
    payload: object = None
```

The simulator therefore models the basic ICMP concepts of:

* message type
* code
* optional payload

---

## Role in CHL

ICMP exists inside the simulated IP layer.

Conceptually:

```text
EthernetFrame
      ↓
IP Packet
      ↓
ICMPPacket
```

The node identifies ICMP traffic and passes it to its ICMP handling path.

---

## Why ICMP matters

ICMP is useful for distinguishing several levels of network functionality.

For example:

```text
Layer 2 works
        ≠
IP routing works
        ≠
TCP port is open
        ≠
Application service works
```

A future simulated ping command can therefore provide a simple diagnostic mechanism without opening a real network socket.

---

## Current scope

The ICMP model is intentionally small.

It currently provides the packet representation and node-level handling required by the simulator rather than implementing every ICMP message type defined by the real protocol.

Potential future additions include:

* Echo Request
* Echo Reply
* Destination Unreachable
* Time Exceeded
* TTL expiration
* routing-error reporting

````

---

## `docs/networking/tcp.md`

```md
# TCP

CHL implements a simulated TCP connection state machine in:

```text
backend/network/tcp.py
````

The primary classes are:

```text
TCPState
TCPConnection
```

TCP traffic is represented by:

```text
TCPPacket
```

from `backend/network/packet.py`.

---

## TCPPacket

A simulated TCP packet contains:

```python
source_port
destination_port
sequence_number
acknowledgement_number
flags
payload
```

Flags are stored as a Python set.

Examples:

```text
SYN
ACK
FIN
RST
```

---

## TCPConnection

A `TCPConnection` tracks one simulated endpoint pair:

```text
local IP
local port
remote IP
remote port
```

It also maintains:

```text
state
sequence number
acknowledgement number
TIME_WAIT timer
network reference
```

---

## Connection states

CHL defines:

```text
LISTEN
SYN_SENT
SYN_RECEIVED
ESTABLISHED

FIN_WAIT1
FIN_WAIT2
CLOSE_WAIT
LAST_ACK
TIME_WAIT

CLOSED
RST
```

The state machine is implemented directly inside `TCPConnection.receive()`.

---

## Active open

A client begins with:

```python
connection.connect()
```

The connection must be:

```text
CLOSED
```

before connecting.

The initial sequence number is set to:

```text
1000
```

and a SYN packet is returned.

The state becomes:

```text
SYN_SENT
```

An event is generated:

```text
TCP_SYN_SENT
```

---

## Passive open

A listening connection enters:

```text
LISTEN
```

through:

```python
connection.listen()
```

When it receives a SYN, it:

1. records the peer sequence number
2. creates its own sequence number
3. enters `SYN_RECEIVED`
4. returns SYN+ACK

The event:

```text
TCP_SYN_RECEIVED
```

is generated.

---

## Establishment

The client receives SYN+ACK and validates its acknowledgement number.

It then:

```text
updates acknowledgement state
increments its sequence number
enters ESTABLISHED
returns ACK
```

The event:

```text
TCP_ESTABLISHED
```

is generated.

The server reaches `ESTABLISHED` after receiving the final ACK.

---

## Data transmission

`send_data()` only works while the connection is:

```text
ESTABLISHED
```

The returned TCP packet contains:

```text
ACK
payload
sequence number
acknowledgement number
```

The sequence number is incremented by the payload length.

A:

```text
TCP_DATA_SENT
```

event is generated.

---

## Data reception

`receive_data()` validates that:

```text
state == ESTABLISHED
```

and that the packet contains an ACK.

It checks the incoming sequence number against the current acknowledgement number.

If valid, the acknowledgement number advances by the payload length.

A:

```text
TCP_DATA_RECEIVED
```

event is generated and an ACK packet is returned.

---

## Closing

Calling:

```python
connection.close()
```

while established generates:

```text
FIN + ACK
```

and transitions to:

```text
FIN_WAIT1
```

The peer transitions through the corresponding close states.

CHL models:

```text
FIN_WAIT1
FIN_WAIT2
CLOSE_WAIT
LAST_ACK
TIME_WAIT
CLOSED
```

---

## TIME_WAIT

TIME_WAIT lasts:

```text
60 seconds
```

in the simulation.

The connection's `tick(seconds)` method decrements the timer.

Once it reaches zero:

```text
TIME_WAIT → CLOSED
```

and:

```text
TCP_CLOSED_TIME_WAIT_EXPIRED
```

is emitted.

---

## Reset

`reset()` generates an RST packet and places the connection into:

```text
CLOSED
```

The event is:

```text
TCP_RESET_SENT
```

A received RST immediately closes the connection and produces:

```text
TCP_RESET_RECEIVED
```

---

## TCP telemetry

TCP generates events including:

```text
TCP_LISTEN
TCP_SYN_SENT
TCP_SYN_RECEIVED
TCP_ESTABLISHED
TCP_DATA_SENT
TCP_DATA_RECEIVED
TCP_FIN_SENT
TCP_FIN_ACK_RECEIVED
TCP_CLOSE_WAIT
TCP_LAST_ACK
TCP_TIME_WAIT
TCP_CLOSED
TCP_RESET_SENT
TCP_RESET_RECEIVED
```

This makes TCP one of the richest current sources of network telemetry in CHL.

---

## Deliberate simplifications

This is not a production TCP implementation.

It does not currently model the complete behavior of:

* congestion control
* retransmission timers
* packet loss/reordering
* receive windows
* sliding windows
* selective acknowledgements
* retransmission queues
* duplicate ACK handling
* TCP options

The state machine exists primarily to make connection behavior and security-relevant events observable.

````

---

## `docs/networking/udp.md`

```md
# UDP

UDP is implemented in:

```text
backend/network/udp.py
````

using:

```text
UDPConnection
UDPPacket
```

## UDP packet

`UDPPacket` contains:

```python
source_port
destination_port
payload
```

Unlike TCP, there is no sequence number, acknowledgement number, or connection state in the packet itself.

---

## UDPConnection

`UDPConnection` stores:

```text
local IP
local port
remote IP
remote port
network
```

The class provides:

```text
send()
receive()
```

---

## Sending

`send(data)` creates a `UDPPacket`.

It also generates:

```text
UDP_DATAGRAM_SENT
```

The event contains:

* source
* destination
* protocol
* destination port
* payload byte count

The resulting packet is then passed back to the node/network processing path.

---

## Receiving

`receive(packet)` returns the packet's payload and generates:

```text
UDP_DATAGRAM_RECEIVED
```

The event records:

* source
* destination
* protocol
* local port
* payload size

---

## UDP versus TCP

The architectural difference is intentional.

TCP:

```text
connection
state machine
sequence numbers
acknowledgements
```

UDP:

```text
datagram
source port
destination port
payload
```

This makes UDP suitable for lightweight simulated services such as DNS and DHCP.

---

## Current limitations

The current UDP implementation does not model:

* packet loss
* packet ordering
* checksum validation
* fragmentation
* congestion behavior
* retransmission

Those behaviors can be added if a future simulation scenario requires them.

````

---

## `docs/networking/dhcp.md`

```md
# DHCP

CHL implements DHCP through two cooperating layers:

```text
backend/network/dhcp.py
backend/network/dhcp_packet.py
````

and DHCP service daemons:

```text
backend/services/dhcp_server.py
backend/services/dhcp_client.py
backend/services/dhcp_relay.py
```

The network-level DHCP manager handles address allocation, while the service layer handles DHCP protocol behavior.

---

## DHCP messages

`backend/network/dhcp_packet.py` defines the DHCP message representation.

The simulator includes the standard message types:

```text
DHCPDISCOVER
DHCPOFFER
DHCPREQUEST
DHCPDECLINE
DHCPACK
DHCPNAK
DHCPRELEASE
```

The message object also represents DHCP header fields such as:

```text
op
htype
hlen
hops
xid
secs
flags
ciaddr
yiaddr
siaddr
giaddr
chaddr
```

and an option dictionary.

---

## DHCP options

Defined option codes include:

```text
Subnet Mask
Router
DNS Server
Requested IP
Lease Time
Message Type
Server Identifier
Parameter Request List
Relay Agent Information
```

This gives the service layer enough information to implement realistic DHCP exchanges without implementing a raw DHCP wire format.

---

# DHCP scopes

`DHCPScope` represents an address pool.

A scope contains:

```text
network
start IP
end IP
gateway
DNS server
lease time
leases
```

For example:

```text
Network: 10.0.0.0/24
Pool:    10.0.0.10 - 10.0.0.254
Gateway: 10.0.0.1
```

---

## Lease states

A lease is stored against a client MAC address.

The lease contains:

```text
IP
expiration time
state
```

The supported states are:

```text
OFFERED
COMMITTED
```

Offered addresses initially have a short 30-second offer lifetime.

Committed leases use the configured scope lease time.

---

## Address allocation

When offering an address, CHL:

1. cleans expired leases
2. checks whether the client already has a valid lease
3. gathers currently used addresses
4. excludes the gateway
5. excludes configured interface addresses
6. finds the first available address in the pool

If no address is available:

```text
DHCP Pool Exhausted
```

is raised.

---

## Lease validation

`validate_lease()` checks that:

* the requested IP belongs to the scope
* it is not allocated to another client
* it is not the gateway
* it is not already configured elsewhere

A valid request becomes a `COMMITTED` lease.

---

## Automatic scope provisioning

If a requested subnet has no DHCP scope, CHL can automatically provision one.

For an IP without an explicit prefix, the implementation infers:

```text
/24
```

The generated scope selects:

* the first usable host as gateway by default
* a pool beginning around the eleventh host
* the second-to-last host as the end of the pool

This is convenience behavior for the simulator, not a universal DHCP convention.

---

## Interface configuration

`DHCP.req_ip()` can assign an address directly to an interface.

After assignment:

```text
interface.ip
interface.subnet
```

are updated.

If the interface's owner supports connected-route installation, that route is installed as well.

This makes DHCP address allocation directly affect the simulated IP routing layer.

---

## DHCP and routing

DHCP is therefore not isolated from the rest of the network stack.

A successful lease can result in:

```text
DHCP
 ↓
interface IP configuration
 ↓
connected route
 ↓
IP connectivity
 ↓
ARP
 ↓
Ethernet
```

---

## Relay

CHL includes a DHCP relay service.

The relay exists because DHCP clients may need to communicate with a server across a routed boundary.

The relay-related packet field is represented through:

```text
giaddr
```

and the relay-agent option is defined in the DHCP packet model.

---

## Security scenarios

DHCP provides useful future offensive/defensive scenarios:

* rogue DHCP servers
* address-pool exhaustion
* unexpected gateway assignment
* unexpected DNS assignment
* lease manipulation

These should remain simulated behaviors rather than real DHCP traffic.

---

### One more important correction

I **would not write a separate generic `networking/network.md` file** even though `network.py` is a major class. Your existing tree doesn't have one, and `networking/` should document *network concepts*, not mirror every Python filename.

Likewise, the docs should **not claim that `mac_aging_time`, STP, VLANs, etc. are implemented** just because configuration fields or scaffolding exist. The distinction between *field exists* and *behavior exists* is exactly the kind of thing the previous documentation got wrong.

Next level should be **`devices/` + `services/`**, because now that the network substrate is nailed down, we can document exactly how `Host`, `Router`, `Switch`, `NetworkInterface`, `Service`, and `ServiceDaemon` fit together.
