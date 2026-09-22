# Network Stack

CHL represents networking as a layered simulation.

A simplified stack is:

```text
Application
   │
TCP / UDP
   │
IP
   │
Ethernet
   │
Interface / Link
```

Supporting protocols such as ARP and DHCP interact with multiple layers.

## Layer responsibilities

### Ethernet

Moves simulated frames between interfaces and switching infrastructure.

### ARP

Resolves IPv4 addresses to simulated MAC addresses.

### IP

Provides logical addressing and determines whether traffic is local or requires routing.

### TCP

Provides connection-oriented transport semantics.

### UDP

Provides connectionless datagram transport.

### Application services

Services such as HTTP, DNS, SSH, and Echo sit above the transport layer.

## Why use objects?

Representing frames and packets as Python objects allows CHL to inspect and visualize traffic instead of hiding everything inside operating-system networking.

This also makes protocol behavior suitable for educational exercises and future offensive/defensive simulations.
