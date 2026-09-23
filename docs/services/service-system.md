# Service System

The service system separates service identity/configuration from protocol behavior.

Relevant areas include:

- `backend/core/service.py`
- `backend/services/base.py`

## Service metadata

Service metadata can describe properties such as:

- service type
- protocol
- port
- state
- host/device association

## Daemons

A service daemon contains the behavior needed to respond to simulated traffic.

This avoids putting HTTP, DNS, SSH, or DHCP logic directly into device classes.

## Extending the system

A new service should generally:

1. define its metadata
2. implement daemon behavior
3. bind to the appropriate transport
4. register itself with the device/service system
5. expose useful telemetry
6. add tests or a reproducible scenario

See [Adding a service](../development/adding-service.md).

## Deliberate design choice

CHL does not currently require a visual scripting system for service behavior. Services are implemented as code because the initial service set is small and protocol behavior is easier to reason about this way.
