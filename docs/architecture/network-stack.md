# Network Stack

Cyber Hazard Lab implements a software-defined network stack using Python objects.

It does not use the host operating system's TCP/IP stack for simulated traffic.

## Objects

The primary packet/frame objects are defined in:

```text
backend/network/packet.py
backend/network/frame.py
```

### IP packet

```python
Packet(
    source_ip,
    destination_ip,
    protocol,
    payload,
    ttl=64
)
```

### Ethernet frame

```python
EthernetFrame(
    source_mac,
    destination_mac,
    payload
)
```

The payload of a `Packet` may contain a transport or control protocol object.

---

## Layer relationship

A normal TCP application request conceptually becomes:

```text
HTTP payload
      ↓
TCPPacket
      ↓
Packet(protocol="TCP")
      ↓
EthernetFrame
      ↓
NetworkInterface
      ↓
Link / Switch
```

A UDP service follows the equivalent path with `UDPPacket`.

ARP is different because `ARPPacket` is carried directly inside an `EthernetFrame`.

---

## Layer-3 processing

`Node.receive_frame()` first checks the Ethernet destination.

If the frame is accepted, its payload is dispatched:

```text
ARPPacket → ARP subsystem

Packet → receive_packet()
```

`Node.receive_packet()` then determines whether the IP packet is:

1. local
2. broadcast
3. routable
4. undeliverable

For local packets, the transport protocol determines the next step.

```text
ICMP → receive_icmp()
UDP  → receive_udp()
TCP  → receive_tcp()
```

---

## Routing

If a packet is not local and forwarding is enabled, the node performs a routing-table lookup.

The implementation uses longest-prefix matching.

```text
Destination IP
      ↓
lookup_route()
      ↓
best matching route
      ↓
outgoing interface
      ↓
ARP next-hop resolution
      ↓
Ethernet transmission
```

Routers enable forwarding; ordinary hosts do not.

---

## ARP

Before an IPv4 packet can be transmitted on an Ethernet segment, the sender may need to resolve the next-hop IP to a MAC address.

If resolution is unavailable:

```text
ARP request
     ↓
packet placed in pending queue
     ↓
ARP reply
     ↓
cache updated
     ↓
pending packets retransmitted
```

---

## Transport

TCP and UDP are implemented as simulation objects.

TCP maintains connection state using `TCPConnection`.

UDP uses `UDPConnection` for datagram transmission/telemetry.

---

## Application services

Once TCP or UDP receives a packet for a configured running service, the node obtains the corresponding service daemon and passes the application payload to it.

```text
Node
 ↓
transport handler
 ↓
Service lookup
 ↓
ServiceDaemon
 ↓
application response
```

This is the most important connection between the simulated network stack and the service system.
