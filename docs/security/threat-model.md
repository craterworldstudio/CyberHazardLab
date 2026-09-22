# Threat Model

CHL itself is an educational simulator, but it still has security boundaries.

## Assets

Important assets include:

- host operating system
- source code
- user files
- simulation state
- browser session
- local API

## Threats

Potential threats include:

### Command escape

A simulated terminal accidentally executes host commands.

### Network escape

A simulated packet path accidentally reaches a real interface.

### Unsafe deserialization

A scenario file causes arbitrary code execution when loaded.

### API abuse

A local API endpoint accepts unexpected input and performs unintended operations.

### Resource exhaustion

A scenario creates unbounded devices, packets, events, or connections.

## Mitigations

- keep simulation objects separate from host resources
- validate API input
- use explicit serialization
- cap unbounded simulation resources
- avoid dynamic code execution
- test hostile inputs

## Penetrator boundary

The offensive simulation layer should attack simulated assets, not the host machine.
