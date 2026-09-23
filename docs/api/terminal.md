# Terminal API

The terminal provides a command-oriented interface to simulated devices.

Relevant application code includes:

- `application/term_coms.py`

## Purpose

The terminal is intended to make device interaction feel closer to working with a real networked system while keeping execution inside the simulator.

## Boundary

Terminal commands should operate on simulated state.

They should not become a mechanism for arbitrary shell execution on the host.

## Future

The terminal can eventually expose commands for:

- interface inspection
- IP configuration
- routing
- ARP
- service management
- diagnostics
- security investigation
