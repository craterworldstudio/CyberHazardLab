# Debugging

Debugging CHL is easiest when the network is traced layer by layer.

## Recommended order

```text
Device exists?
   ↓
Interface exists?
   ↓
Link connected?
   ↓
MAC resolution works?
   ↓
IP routing works?
   ↓
Transport works?
   ↓
Service is running?
   ↓
Application request works?
```

## Event inspection

Use simulation events to determine where traffic stops.

For example:

```text
DHCP_LEASE
SERVICE_CREATED
ARP_REPLY
FRAME_RECEIVED
FRAME_FLOODED
```

These events can reveal whether a failure is occurring at discovery, forwarding, transport, or application level.

## Frontend debugging

If the backend state is correct but the UI is wrong:

1. inspect API responses
2. inspect browser console
3. verify frontend state updates
4. verify DOM rendering

Do not immediately modify backend protocol logic when the problem is only presentation.
