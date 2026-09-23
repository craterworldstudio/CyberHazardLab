# Simulation API

Simulation endpoints provide access to the simulated laboratory state and actions.

The exact endpoint set can evolve as the simulator grows.

## Typical operations

A simulation API may need to support:

- retrieving current topology
- retrieving device state
- creating/removing objects
- starting or restarting simulated components
- retrieving events
- executing simulation actions

## Response principle

Responses should contain data suitable for frontend rendering rather than leaking internal Python object structures.

## Future

A versioned API may eventually become useful if external clients or automated scenario tools are supported.
