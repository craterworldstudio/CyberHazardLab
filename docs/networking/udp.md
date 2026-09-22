# UDP

UDP provides lightweight connectionless transport.

Unlike TCP, UDP does not establish a connection before sending a datagram.

## Characteristics

A simulated UDP datagram can be associated with:

- source port
- destination port
- payload

## Services

UDP is appropriate for protocols where connection establishment is unnecessary or undesirable.

DHCP and DNS are important examples in the CHL service model.

## Educational contrast

TCP and UDP should remain visibly different in the simulator:

```text
TCP → connection-oriented
UDP → datagram-oriented
```

This distinction is important for understanding network services and security behavior.
