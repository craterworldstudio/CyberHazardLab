# NCM Frontend

The NCM frontend provides device-management windows.

## Window system

NCM maintains open device windows using a global window collection and provides operations such as:

- `openNCM`
- `closeNCM`
- `createNCMWindow`

## Tabs

The current UI concept includes:

- HEALTH
- CONFIG
- SERVICES or device-specific forwarding tables
- INTERFACES

Switches may display a MAC table, while routers may display a routing table.

## API interaction

NCM retrieves information through dedicated backend endpoints.

The frontend should treat returned data as state to display, not as permission to modify arbitrary backend structures.
