# API Overview

The application API is the bridge between the browser and the simulation.

Primary implementation:

- `application/api.py`

## Endpoint categories

CHL exposes endpoints for:

- simulation operations
- NTM
- NCM
- device information
- interfaces
- health
- services
- restart operations
- terminal communication

## General request flow

```text
JavaScript
  ↓
HTTP request
  ↓
API route
  ↓
Backend object
  ↓
Operation
  ↓
JSON response
```

## Design rule

API routes should orchestrate backend behavior, not reimplement the simulation engine.
