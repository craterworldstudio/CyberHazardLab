# Adding a Service

Services are implemented as simulated daemons rather than real host processes.

## Process

1. Define service metadata.
2. Create or extend a daemon implementation.
3. Select the appropriate transport.
4. Define request/response behavior.
5. Attach the service to a device.
6. Emit useful events.
7. Expose it through NCM if appropriate.
8. Test a complete client/server interaction.

## Avoid

Do not create a new service by embedding all behavior into `device.py`.

Do not open a real TCP/UDP socket on the host unless a future architecture explicitly requires it and isolation has been designed.

## Example

An HTTP service should depend on simulated TCP, not Python's real `socket` module.
