# Ethernet

Ethernet is the simulated link-layer foundation of CHL.

## Frames

The implementation uses a simulated frame representation rather than the host machine's physical network interface.

A frame conceptually contains:

- source MAC
- destination MAC
- payload
- frame metadata

## Delivery

Frames are delivered through simulated interfaces and links.

A switch may:

1. Receive a frame.
2. Learn the source MAC.
3. Look up the destination MAC.
4. Forward to the appropriate port.
5. Flood when the destination is unknown or broadcast.

## Broadcast

Broadcast frames are important for protocols such as ARP and DHCP.

CHL can emit telemetry for frame reception and flooding, making forwarding behavior visible to the observer layer.

## Source

Relevant implementation is primarily under:

- `backend/network/frame.py`
- `backend/network/link.py`
- `backend/core/interface.py`
- `backend/network/switch.py`
