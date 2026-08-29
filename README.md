
# 🛡️ SOC LAB Simulation

> **Course Project:** This was CS50! Built by **Soulfire**.

<!-- 🎥 Video Demo: <YOUR_URL_HERE> -->

## 📝 Description

**SOC LAB** is an interactive Security Operations Center (SOC) simulation environment. It features a **real, fully isolated network simulation** running in the background, making it entirely self-contained. 

Designed specifically for students and aspiring network/security professionals, this platform offers a safe environment to learn core networking concepts and practical security monitoring. Additionally, the project includes a **Manual Penetrator Dashboard**—allowing users to safely launch cyber attacks against their own simulated infrastructure to see how a SOC catches real-world threats without risking actual damage.

---

## 🚀 Core Features

*   **Isolated Network Backend:** A full software-defined networking sandbox simulating real nodes, frames, and packets.
*   **Dual Perspectives:** Switch between defensive monitoring (SOC Analyst) and active offensive testing (Penetrator).
*   **No-Risk Exploitation:** Safely execute attacks and view their immediate impact on network telemetry.

---

## 🛠️ Built With

*   Python

---

## 🗺️ Roadmap & Development Progress

### 📊 Overview

| Phase | Description | Progress | Status |
| :--- | :--- | :--- | :---: |
| **Phase 1** | Foundation             | `████████████████████` 4/4 | ✅ Done |
| **Phase 2** | Local Networking       | `██████████████████░░` 8/9 | ✅ Done |
| **Phase 3** | Transport Layer        | `████████░░░░░░░░░░░░` 3/8 | 🟡 In Progress |
| **Phase 4** | Network Infrastructure | `████████████░░░░░░░░` 3/5 | 🟡 In Progress |
| **Phase 5** | Application Layer      | `░░░░░░░░░░░░░░░░░░░░` 0/4 | ❌ Not Started |
| **Phase 6** | SOC Integration        | `███░░░░░░░░░░░░░░░░░` 1/6 | 🟡 In Progress |
| **Phase 7** | Penetrator Dashboard   | `░░░░░░░░░░░░░░░░░░░░` 0/5 | ❌ Not Started |

---

### 🔍 Detailed Phase Breakdown

#### PHASE 1 — Foundation ✅
- [x] Host configuration
- [x] Interface abstraction
- [x] Service handling
- [x] Event logging pipeline

#### PHASE 2 — Local Networking ✅
- [x] DHCP protocol simulation
- [x] ARP resolution
- [x] IP Packet implementation
- [x] Ethernet Frame structure
- [x] Physical/Logical Link boundaries
- [x] Layer 2 Switch emulation
- [x] ARP → Ethernet integration
- [x] Multi-Switch network environments
- [ ] Network orchestrator

#### PHASE 3 — Transport Layer 🟡
- [x] ARP integration
- [x] ARP cache tables
- [x] IP packet forwarding
- [ ] TCP state machine
- [ ] UDP communication
- [ ] TCP 3-way handshake simulation
- [/] Active connection management
- [ ] Raw data streams

#### PHASE 4 — Network Infrastructure 🟡
- [x] Router integration
- [x] Routing table engines
- [x] Multiple subnet routing
- [ ] DNS resolution architecture
- [ ] State-based Firewall

#### PHASE 5 — Application Layer ❌
- [ ] HTTP protocol support
- [ ] Core DNS services
- [ ] Secure Shell (SSH) emulation
- [ ] Fully integrated DHCP services

#### PHASE 6 — SOC Integration 🟡
- [x] Network Telemetry generation
- [ ] Packet & event ingestion engines
- [ ] Custom detection rule matching
- [ ] Real-time alerting framework
- [ ] Security operations monitoring dashboard
- [ ] Incident investigation workflows

#### PHASE 7 — Penetrator Dashboard ❌
- [ ] Active port scanning utilities
- [ ] Host discovery engines
- [ ] Service enumeration
- [ ] Automated network traffic generation
- [ ] Cyber attack simulations

---
