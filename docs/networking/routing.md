# Routing

Routing determines where an IP packet should be forwarded when its destination is not directly connected.

## Router responsibilities

A simulated router can:

- receive an IP packet
- inspect its destination
- consult routing information
- select an outgoing interface
- forward the packet

## Routing table

Router state may contain entries describing:

```text
Destination
Prefix / mask
Next hop
Interface
Metric or preference
```

The exact internal representation is an implementation detail and may evolve.

## Default route

A default route provides a fallback for destinations not matched by a more specific route.

## Future work

Potential future additions include:

- dynamic routing protocols
- route metrics
- administrative distance
- route failure simulation
- packet TTL handling
- richer ICMP errors
