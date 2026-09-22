# Services Overview

CHL models application services as simulated daemons running on devices.

Current service concepts include:

- DHCP
- DNS
- HTTP
- SSH
- Echo

Services are not real processes and do not open real host ports.

## Service lifecycle

A typical service lifecycle is:

```text
Service metadata
      ↓
Service created
      ↓
Daemon instantiated
      ↓
Daemon attached to device
      ↓
Listening / available
      ↓
Requests handled
```

## Why services are objects?

This lets CHL model service availability, configuration, telemetry, and attacks without requiring real network exposure.
