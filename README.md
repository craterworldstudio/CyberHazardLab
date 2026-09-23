
# 🛡️ Cyber Hazard Lab

## 📝 Description

**Cyber Hazard Lab** is an interactive Security Operations Center (SOC) simulation environment. It features a **real, fully isolated network simulation** running in the background, making it entirely self-contained. 

Designed specifically for students and aspiring network/security professionals, this platform offers a safe environment to learn core networking concepts and practical security monitoring. Additionally, the project includes a **Manual Penetrator Dashboard**—allowing users to safely launch cyber attacks against their own simulated infrastructure to see how a SOC catches real-world threats without risking actual damage.

---

## 🚀 Core Features

*   **Isolated Network Backend:** A full software-defined networking sandbox simulating real nodes, frames, and packets.
*   **Dual Perspectives:** Switch between defensive monitoring (SOC Analyst) and active offensive testing (Penetrator).
*   **No-Risk Exploitation:** Safely execute attacks and view their immediate impact on network telemetry.

---

## 🛠️ Built With

*   Python
*   Html5
*   Css
*   Javascript

---

## 🗺️ Roadmap & Development Progress

### 📊 Overview

| Phase | Description | Progress | Status |
| :--- | :--- | :--- | :---: |
| **Phase 1** | Foundation               | `████████████████████` 4/4   | ✅ Done |
| **Phase 2** | Local Networking         | `████████████████████` 9/9   | ✅ Done |
| **Phase 3** | Transport Layer          | `████████████████████` 8/8   | ✅ Done |
| **Phase 4** | Network Infrastructure   | `████████████░░░░░░░░` 7/12  | 🟡 In Progress |
| **Phase 5** | Application Layer        | `███████████░░░░░░░░░` 3/6   | 🟡 In Progress |
| **Phase 6** | Interactive Lab Frontend | `███████████████████░` 14/15 | 🟡 In Progress |
| **Phase 7** | SOC Integration          | `███░░░░░░░░░░░░░░░░░` 1/6   | 🟡 In Progress |
| **Phase 8** | Penetrator Dashboard     | `░░░░░░░░░░░░░░░░░░░░` 0/5   | ❌ Not Started |


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
- [x] Network orchestrator

#### PHASE 3 — Transport Layer ✅
- [x] ARP integration
- [x] ARP cache tables
- [x] IP packet forwarding
- [x] TCP state machine
- [x] UDP communication
- [x] TCP 3-way handshake simulation
- [x] Active connection management
- [x] Raw data streams

#### PHASE 4 — Network Infrastructure 🟡
- [x] Router integration
- [x] Routing table engines
- [x] Multiple subnet routing
- [x] ICMP Communication
- [x] Ping Devices
- [x] Traceroute
- [x] Dynamic network topology management
- [ ] DNS resolution architecture
- [ ] State-based Firewall & ACLs
- [ ] IDS/IPS Node Simulation
- [ ] NAT (Network Address Translation)
- [ ] L1 Hub Emulation

#### PHASE 5 — Application Layer 🟡
- [ ] HTTP/HTTPS protocol support
- [ ] Core DNS services
- [x] Secure Shell (SSH) emulation
- [x] Echo Service Integration
- [ ] Custom Service Script Execution Engine
- [x] Fully integrated DHCP services

#### PHASE 6 — Interactive Lab Frontend 🟡
- [x] RESTful API architecture and serialization (`api.py`)
- [x] Interactive Topology Floor (Drag & drop nodes, tools palette)
- [x] Dynamic SVG wire connections
- [x] Device State and Lifecycle syncing (Validate/Run/Stop)
- [x] Draggable Window Manager System
- [x] Network Configuration Manager (NCM) per-device tabs
- [x] Global NCM (Network Alerts, Global Subnets)
- [x] Interface & SwitchPort physical assignment API
- [x] Service spawning and management via UI
- [x] Device node hardware resets and error state rendering
- [x] NCM Terminal (Interactive console for devices, e.g. ping, tracert, ipconfig/ifconfig, hostname, netsh, netstat, ss, arp, nslookup)
- [x] Payload Manager (Manual ICMP/TCP/UDP packet forging)
- [x] Dynamic MAC Learning & Routing Table UI visualization
- [x] PingSweep and TraceRoute Integration via Validate
- [ ] PCAP Export (Download traffic captures for Wireshark)


#### PHASE 7 — Application Integration 🟡
- [x] Network Telemetry generation
- [ ] Packet & event ingestion engines
- [ ] Custom detection rule matching
- [ ] Real-time alerting framework
- [ ] Security operations monitoring dashboard
- [ ] Incident investigation workflows

#### PHASE 8 — Penetrator Dashboard ❌
- [ ] Active port scanning utilities
- [ ] Host discovery engines
- [ ] Service enumeration
- [ ] Automated network traffic generation
- [ ] Cyber attack simulations


---

---

## 🛠️ Installation & Local Setup

Because the backend utilizes state-centric memory structures to execute live routing topologies, **local execution via loopback (`127.0.0.1`) is the recommended way to experience isolated laboratory environments.**

### Prerequisites
* **Python 3.10+** (No third-party package dependencies required for core execution)
* Any modern web browser

### Setup Instructions

1. **Clone the repository framework:**
   ```bash
   git clone https://github.com
   cd cyberhazardlab
   ```

2. **Initialize the local orchestration server:**
   ```bash
   python application/main.py
   ```
   *The server dynamically binds to `127.0.0.1:8000` locally. If deployed to cloud runtimes ([CyberHazard Lab](https://cyberhazardlab.onrender.com)), it automatically switches interface bindings to comply with host proxy architecture.*

3. **Access the Interface:**
   Launch your browser and navigate to: `http://127.0.0.1:8000`
---

## 🔒 Threat Vector Insulation & Sandboxing

Cyber Hazard Lab is built from the ground up to guarantee environment containment:
* **Air-Gapped Execution:** Packet processing engines (`Packet`, `TCPPacket`) exist purely as structured Python object instances. The backend handles no raw host socket hooks (`socket.AF_PACKET`), preventing traffic leakage outside the application process.
* **Deterministic Lexical Terminal:** The integrated console uses an isolated token parsing matrix (`if command.startswith("ping")`) rather than exposing input arguments to system execution environments (`os.system` / `subprocess`). The application is natively safe from command injection bypasses.

