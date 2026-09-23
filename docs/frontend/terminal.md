# Terminal Frontend

The terminal frontend presents a command-line interface for interacting with simulated devices.

## Goals

The terminal should feel familiar to users with networking or Linux experience while remaining constrained to the simulation.

## Command flow

```text
User input
  ↓
Terminal UI
  ↓
Application terminal handler
  ↓
Simulated device
  ↓
Result
  ↓
Terminal UI
```

## Safety boundary

Terminal commands must not escape the simulator and execute arbitrary host commands.

See [Isolation](../security/isolation.md).
