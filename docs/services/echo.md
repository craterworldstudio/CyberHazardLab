# Echo Service

The Echo service is a deliberately simple application service.

Its purpose is to provide a minimal end-to-end communication target.

## Why it exists

Echo is useful for testing the complete simulated stack without requiring complicated application semantics.

```text
Client
 ↓
Transport
 ↓
Echo service
 ↓
Transport
 ↓
Client
```

It is also useful when debugging new networking functionality.
