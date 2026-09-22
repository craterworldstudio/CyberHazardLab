# Architecture Guidelines

These guidelines keep CHL understandable as it grows.

## 1. Backend owns simulation state

Do not make the browser authoritative.

## 2. Protocols remain separate

ARP should not contain routing logic. TCP should not contain HTTP semantics. HTTP should not know how Ethernet forwarding works.

## 3. Devices provide composition

Devices contain interfaces and services rather than implementing every protocol themselves.

## 4. Services are modular

Application services should implement their own behavior behind a common service abstraction.

## 5. Events are first-class

Important simulation actions should produce events where practical.

## 6. APIs orchestrate

API handlers should translate HTTP requests into backend operations.

## 7. Prefer explicit behavior

Networking simulations benefit from code that is easy to trace. Clever abstractions are less valuable than understandable protocol flows.

## 8. Keep real networking out

The simulator should not accidentally transmit arbitrary traffic onto the host network.
