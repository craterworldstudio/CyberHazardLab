# ARP

Address Resolution Protocol is implemented in:

```text
backend/network/arp.py
````

CHL uses ARP to resolve an IPv4 address into a simulated MAC address before transmitting an IP packet across an Ethernet segment.

## ARP ownership

ARP is instantiated for a node.

Each ARP instance maintains:

```python
self.cache
self.pending_queue
```

The cache maps:

```text
IP address → MAC address
```

For example:

```text
10.0.0.1 → AA:BB:CC:DD:EE:FF
```

The pending queue stores packets that cannot yet be transmitted because MAC resolution has not completed.

---

## Resolution

The main operation is:

```python
arp.resolve(...)
```

If the requested IP already exists in the cache, its MAC address is returned immediately.

If it does not exist and a source interface was provided, CHL sends an ARP request.

Conceptually:

```text
resolve(10.0.0.1)
        │
        ├── cached → return MAC
        │
        └── unknown
              ↓
        send ARP request
              ↓
        return None
```

---

## ARP request

`ARP.request()` creates an `ARPPacket`:

```text
operation = REQUEST
sender_ip = interface IP
sender_mac = interface MAC
target_ip = requested IP
```

It then wraps the packet in an Ethernet broadcast frame:

```text
Destination MAC:
FF:FF:FF:FF:FF:FF
```

The frame is transmitted through the source interface.

An `ARP_REQUEST` event is also generated.

---

## ARP request processing

When a node receives an ARP request, it checks:

```text
Does target_ip equal this interface's IP?
```

If not, it ignores the request.

If yes, it:

1. learns the sender's MAC address
2. creates an ARP reply
3. addresses the reply to the sender's MAC
4. transmits the reply

This means CHL performs passive learning from ARP requests as well as explicit learning from replies.

---

## ARP reply

When an ARP reply arrives:

```text
sender IP → sender MAC
```

is inserted into the local ARP cache.

The simulator generates an:

```text
ARP_REPLY
```

event.

---

## Pending packet queue

An important part of the implementation is that packets do not simply disappear when ARP resolution is unavailable.

`ARP.enqueue()` stores:

```text
(target IP) → [(packet, interface), ...]
```

When the corresponding ARP reply arrives, CHL:

1. removes the pending queue entry
2. retrieves each queued packet
3. calls `node.send_ip_packet()`
4. sends the packet using the now-known MAC address

Conceptually:

```text
IP packet wants 10.0.0.5
        ↓
ARP cache miss
        ↓
queue packet
        ↓
ARP request
        ↓
ARP reply
        ↓
cache updated
        ↓
flush pending queue
        ↓
send original IP packet
```

---

## What CHL does not currently model

The ARP implementation is intentionally simplified.

It does not currently model the full range of real ARP behavior, including:

* ARP cache expiration
* gratuitous ARP
* ARP probes
* duplicate-address detection
* ARP poisoning as a native protocol feature
* retransmission timers
* negative ARP caching

Those can be implemented later as simulation features or offensive-security scenarios.

---

## Security relevance

ARP is particularly useful for CHL because it provides a natural foundation for future simulated attacks.

For example, a future Penetrator module could manipulate simulated ARP behavior without touching the real network.

The current ARP implementation itself remains a normal protocol subsystem.

 ----
