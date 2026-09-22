# DHCP Service

DHCP services automatically assign network configuration to simulated clients.

CHL includes server, client, and relay components.

Relevant files:

- `backend/services/dhcp_server.py`
- `backend/services/dhcp_client.py`
- `backend/services/dhcp_relay.py`

## Server

The server manages available leases and responds to DHCP messages.

## Client

A client requests configuration rather than requiring a manually assigned address.

## Relay

A relay forwards DHCP traffic between client networks and a remote DHCP server.

## Security relevance

DHCP is useful for future attack/defense scenarios involving rogue servers, lease exhaustion, and unexpected configuration changes.
