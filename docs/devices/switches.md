# Switches

Switches operate primarily at the simulated Ethernet layer.

## Core behavior

A switch maintains forwarding knowledge based on observed source MAC addresses.

```text
Frame received
      ↓
Learn source MAC
      ↓
Find destination MAC
   ↙       ↘
Known      Unknown
  ↓           ↓
Forward     Flood
```

## Management

NCM can expose switch information such as interface state and the MAC table.

## Future extensions

Possible features include VLANs, trunks, STP, port security, and MAC aging.
