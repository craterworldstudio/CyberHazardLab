# DHCP

Dynamic Host Configuration Protocol provides automatic network configuration.

## Basic exchange

The familiar DHCP process is:

```text
DISCOVER
   ↓
OFFER
   ↓
REQUEST
   ↓
ACK
```

This is commonly called DORA.

## CHL implementation

DHCP functionality is distributed between the network and service layers.

Relevant files include:

- `backend/network/dhcp.py`
- `backend/network/dhcp_packet.py`
- `backend/services/dhcp_server.py`
- `backend/services/dhcp_client.py`
- `backend/services/dhcp_relay.py`

## Simulated lease

A lease associates a client with an assigned IP address and related configuration.

The event system can expose lease creation so that future SOC functionality can observe DHCP activity.

## Relay

A DHCP relay allows DHCP traffic to cross a routed boundary without requiring a DHCP server on every local network.
