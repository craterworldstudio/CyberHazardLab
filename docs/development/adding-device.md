# Adding a Device

A new device type should be implemented as a backend simulation object before adding UI controls.

## Suggested process

### 1. Define the device model

Determine:

- device identity
- interfaces
- supported protocols
- services
- device-specific state

### 2. Implement backend behavior

Add the device to the appropriate core/backend module.

### 3. Add protocol behavior

Only add protocol behavior that belongs specifically to the device.

### 4. Register with topology management

Make the device available to NTM.

### 5. Add API representation

Expose only the state needed by the frontend.

### 6. Add frontend representation

Add topology visuals and NCM views where necessary.

### 7. Test

Test:

- creation
- interfaces
- connectivity
- restart
- deletion if supported
- state serialization
