# ARP

Address Resolution Protocol maps IPv4 addresses to MAC addresses on a local network.

## Basic flow

```text
Host A
  │
  │ ARP Request: Who has 10.0.0.1?
  ▼
Broadcast
  │
  ▼
Host/Router owning 10.0.0.1
  │
  │ ARP Reply
  ▼
Host A
```

## Simulation behavior

CHL represents ARP activity internally and can emit events such as ARP replies.

An ARP cache can then be used to avoid repeating resolution unnecessarily.

## Relationship with Ethernet

ARP itself is carried as a link-layer message. It is therefore processed before ordinary IPv4 delivery can occur when a destination MAC is unknown.

## Educational value

ARP is intentionally visible because it is a useful bridge between Layer 2 and Layer 3 concepts and is relevant to many network-security scenarios.
