# Frontend Architecture

The frontend is a browser application implemented with HTML, CSS, and JavaScript.

The frontend is deliberately separated from the simulation engine.

## Main frontend responsibilities

- Render the laboratory interface.
- Display topology.
- Create and manipulate UI windows.
- Request simulation state.
- Send user actions to the backend.
- Display device configuration and health.
- Provide terminal interaction.

## Important JavaScript areas

Typical frontend modules include:

- `application/static/js/api.js`
- `application/static/js/lab_app.js`
- `application/static/js/ncm_app.js`
- `application/static/js/topology.js`
- `application/static/js/wel_app.js`

## State rule

Frontend state may cache information for presentation, but authoritative simulation state remains in Python.

## NCM

NCM provides device-oriented management windows with areas such as:

- HEALTH
- CONFIG
- SERVICES or forwarding tables depending on device type
- INTERFACES

The NCM frontend communicates with dedicated API endpoints rather than directly manipulating backend objects.
