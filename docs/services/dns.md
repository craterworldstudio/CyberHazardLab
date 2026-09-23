# DNS Service

DNS translates names into addresses.

## Conceptual request

```text
Client
  │
  │ DNS query
  ▼
DNS server
  │
  │ response
  ▼
Client
```

## Transport

DNS commonly uses UDP for ordinary queries, although real DNS can also use TCP in specific circumstances.

The simulator can use its own transport abstractions rather than the host network.

## Educational use

DNS provides a useful application-layer example for:

- name resolution
- service discovery
- cache behavior
- spoofing scenarios in future security modules
