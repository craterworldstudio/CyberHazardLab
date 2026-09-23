# IP

The simulated IP layer provides logical addressing and packet delivery.

## Responsibilities

IP processing determines:

- source address
- destination address
- local versus remote delivery
- next-hop requirements
- interaction with routing

## Local delivery

If a destination belongs to a directly connected network, the sender can resolve its MAC address and deliver the packet locally.

## Routed delivery

For another network:

```text
Host
  ↓
Default Gateway
  ↓
Router
  ↓
Destination Network
  ↓
Host
```

The router decides where the packet should go using its routing information.

## Source

Relevant implementation includes `backend/network/packet.py` and `backend/network/router.py`.
