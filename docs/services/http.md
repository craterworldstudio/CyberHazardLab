# HTTP Service

The HTTP service simulates a web server at the application layer.

## Stack

```text
HTTP
 ↓
TCP
 ↓
IP
 ↓
Ethernet
```

## Typical lifecycle

A client connects to the simulated HTTP port, establishes a TCP connection, sends an HTTP request, and receives a simulated response.

## Educational use

HTTP is useful for demonstrating:

- ports
- TCP connections
- client/server behavior
- service discovery
- application-layer attacks in future Penetrator scenarios

The service remains entirely inside the CHL simulation.
