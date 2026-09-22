# Switching

CHL models Ethernet switching as software.

## MAC learning

A switch learns where a source MAC address was observed:

```text
MAC A → Port 1
MAC B → Port 3
```

When a frame arrives for a known destination, it can be forwarded to the corresponding port.

## Flooding

If the destination is unknown, or if the frame is broadcast, the switch can flood it across the relevant ports.

This behavior is observable through simulation events.

## Source

Important implementation areas include:

- `backend/network/switch.py`
- `backend/network/switchport.py`

## Future extensions

Possible additions include:

- VLANs
- trunk ports
- STP concepts
- port states
- MAC aging
- broadcast domains
