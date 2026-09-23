# API Architecture

The application layer exposes HTTP endpoints that translate browser actions into backend operations.

```text
Browser
  │ HTTP
  ▼
application/api.py
  │
  ▼
Simulation backend
```

## Responsibilities

The API layer should:

1. Validate incoming requests.
2. Locate the requested simulated object.
3. Invoke an appropriate backend operation.
4. Serialize the result.
5. Return an HTTP response.

It should not contain the actual implementation of protocols such as ARP, TCP, or routing.

## Endpoint families

CHL has endpoint families for:

- simulation state and actions
- NTM
- NCM
- device information
- interfaces
- health
- services
- restart operations

See the [API overview](../api/overview.md) for the current interface map.

## Error handling

API errors should describe invalid requests without exposing internal implementation details unnecessarily.

The API should also distinguish between:

- malformed requests
- unknown devices
- invalid actions
- simulation-level failures
