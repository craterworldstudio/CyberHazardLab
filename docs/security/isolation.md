# Simulation Isolation

Isolation is a core safety property of Cyber Hazard Lab.

## Fundamental rule

Simulated traffic should remain simulated.

The project models cybersecurity behavior without intentionally injecting arbitrary packets into the host's physical network.

## Host boundary

The simulation should not:

- execute arbitrary terminal commands from simulated devices
- expose simulated services on host ports by default
- transmit simulated Ethernet frames through physical interfaces
- treat simulation input as trusted operating-system commands

## Why this matters

CHL is intended to support offensive-security education. A vulnerable simulation is useful; an accidentally exposed real service is not.

## Future sandboxing

If CHL ever adds intentionally dangerous functionality, it should be isolated behind additional controls such as:

- explicit opt-in
- process isolation
- containers or VMs
- network namespaces
- resource limits
- clear separation between simulation and host execution
