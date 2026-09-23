# TCP

TCP is the simulated connection-oriented transport protocol.

## Purpose

TCP provides:

- connection establishment
- ordered delivery
- retransmission concepts
- connection termination
- application port addressing

## Connection lifecycle

A simplified lifecycle is:

```text
CLOSED
  │
  ▼
SYN
  │
  ▼
SYN-ACK
  │
  ▼
ACK
  │
  ▼
ESTABLISHED
  │
  ▼
FIN / ACK
  │
  ▼
CLOSED
```

The implementation does not need to reproduce every behavior of a production TCP stack to model these concepts.

## Services

TCP services can bind to simulated ports, for example HTTP or SSH.

## Source

Primary implementation is in `backend/network/tcp.py`, with application protocol behavior in service modules.

## Limitations

The simulator may simplify:

- congestion control
- retransmission timers
- sequence-number handling
- packet loss
- window scaling
- out-of-order delivery

These can be added later if they improve educational scenarios.
