# Penetrator

Penetrator is the planned offensive-security layer of Cyber Hazard Lab.

It is conceptually separate from the network simulation itself.

## Purpose

Penetrator can eventually provide simulated attack behavior such as:

- reconnaissance
- service discovery
- network enumeration
- protocol abuse
- simulated exploitation
- credential attacks
- lateral movement

## Architecture

The intended relationship is:

```text
Penetrator
    ↓
Simulation interfaces
    ↓
Simulated network
    ↓
Simulated target
```

Penetrator should not directly call the host operating system or send arbitrary traffic onto the real network.

## Why keep it separate?

Keeping offensive behavior separate from the protocol engine makes the project easier to reason about.

The same simulated network can then support:

- normal operation
- defensive monitoring
- offensive scenarios
- SOC investigations

## Future

A mature Penetrator system could use the event stream to observe consequences of simulated attacks and generate scenarios for the future SOC interface.
