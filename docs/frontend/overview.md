# Frontend Overview

The frontend provides the interactive laboratory environment.

It is built using browser-native technologies rather than a large frontend framework.

## Main areas

- welcome/start screen
- topology workspace
- device management windows
- terminal
- future SOC/observer interfaces

## JavaScript modules

Important modules include:

- `api.js`
- `lab_app.js`
- `ncm_app.js`
- `topology.js`
- `wel_app.js`

## Communication

Frontend modules should use the API layer instead of reaching directly into backend implementation details.
