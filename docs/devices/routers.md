# Routers

Routers connect different IP networks.

## Core behavior

A router:

1. receives traffic on an interface
2. determines whether it can process or forward the packet
3. consults routing information
4. selects an outgoing interface
5. forwards the traffic

## Management

NCM can expose router-specific information such as interfaces and routing information.

## Future extensions

Potential future router features include:

- static route configuration UI
- dynamic routing
- ACLs
- NAT
- route failure simulation
- richer ICMP behavior
