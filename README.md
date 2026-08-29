# SOC LAB
<!-- #### Video Demo:  <URL HERE> -->
#### Description:
Hello, this is Soulfire and This was Cs50!
I am building a SOC LAB Simulation with a real Network Simulation Running in the Background on a complete Isolated Backend which is self contained by nature purely for learning about networking and networks and people who want to be a SOC Analyst! There is additionally a Mannual Penetrator Dashboard too so you can attack your OWN System but not break it!


## Plans
### PHASE 1 — Foundation              ✅
├── Host
├── Interface
├── Service
└── Event

### PHASE 2 — Local networking        ✅
├── DHCP                          ✅
├── ARP                           ✅
├── IP Packet                     ✅
├── Ethernet Frame                ✅
├── Plysical/Logical Links        ✅
├── Switch                        ✅
├── ARP → Ethernet integration    ✅
├── Multi Switch Integration      ✅
└── Network orchestrator

### PHASE 3 — Transport           🟡
├── ARP                          ✅
├── ARP cache                    ✅
├── IP packets                   ✅
├── TCP
├── UDP
├── TCP handshake
├── Connections                   🟡
└── Data streams

### PHASE 4 — Network infrastructure 🟡
├── Router                           ✅
├── Routing table                    ✅
├── Multiple subnets                 ✅
├── DNS
└── Firewall

### PHASE 5 — Applications          🟡
├── HTTP
├── DNS service
├── SSH
├── DHCP service
└── etc.
 
### PHASE 6 — SOC                 🟡
├── Telemetry                       ✅
├── Packet/event ingestion
├── Detection rules
├── Alerts
├── Dashboard
└── Investigation

### PHASE 7 — Penetrator               🟡
├── Port scanning
├── Host discovery
├── Service enumeration
├── Traffic generation
└── Attack simulation



PHASE 1 — Foundation
████████████████████  4/4 ✅

PHASE 2 — Local networking
██████████████████░░  8/9 ✅

PHASE 3 — Transport
░░░░░░░░░░░░░░░░░░░░  0/4 ❌

PHASE 4 — Network infrastructure
████████████░░░░░░░░  3/5 ✅

PHASE 5 — Applications
░░░░░░░░░░░░░░░░░░░░  0/4 ❌

PHASE 6 — SOC
███░░░░░░░░░░░░░░░░░  1/6 🟡

PHASE 7 — Penetrator
░░░░░░░░░░░░░░░░░░░░  0/5 ❌


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
