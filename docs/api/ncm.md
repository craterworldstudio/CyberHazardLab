# NCM API

NCM means **Network Configuration Manager**.

It exposes device-management information and actions to the frontend.

## Current endpoint patterns

The frontend uses endpoint patterns including:

```text
/api/ncm/devices/{device}/interfaces
/api/ncm/devices/{device}/health
/api/ncm/devices/{device}/services
/api/ntm/devices/{device}
```

Restart functionality is exposed through:

```text
POST /api/ncm/devices/{device}/restart
```

## Device-specific views

NCM adapts information to the device type.

For example:

- switches can expose MAC tables
- routers can expose routing information
- hosts can expose services

## Frontend

The NCM application maintains multiple management windows and tabs. See [NCM frontend](../frontend/ncm.md).
