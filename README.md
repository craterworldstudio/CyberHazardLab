
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

## 🛠️ Installation, Standalone & Docker Execution

Because the backend utilizes state-centric memory structures to execute live routing topologies, **local execution via loopback (`127.0.0.1`) is the recommended way to experience isolated laboratory environments.**

### Option 1: Native Python
```bash
python -m pip install -r requirements.txt
python application/main.py
```
Then navigate to: `http://127.0.0.1:8000`

### Option 2: Docker Container (Docker Compose)
Run with persistent state storage:
```bash
docker-compose up --build -d
```
Or with standard Docker:
```bash
docker build -t cyberhazardlab .
docker run -d -p 8000:8000 -p 514:514/udp -v $(pwd)/simulation_state.json:/app/simulation_state.json cyberhazardlab
```

### Option 3: Standalone Executable (No Python Required)
Build self-contained, zero-dependency executable distributions:

* **Linux:**
  ```bash
  chmod +x build_linux.sh
  ./build_linux.sh
  # Run the binary:
  ./dist/CyberHazardLab/CyberHazardLab
  ```

* **Windows:**
  Double-click `build_windows.bat` or run:
  ```powershell
  .\build_windows.ps1
  # Run the binary:
  .\dist\CyberHazardLab\CyberHazardLab.exe
  ```

---

## 🧭 Navigation Endpoints
* **Welcome Portal:** `http://localhost:8000/` or `/welcome`
* **Net.Creator (Network Builder & NCM):** `http://localhost:8000/lab`
* **Net.Observer (Defensive SOC Dashboard):** `http://localhost:8000/soc`
* **Net.Attacker (Offensive Red Team Terminal):** `http://localhost:8000/attacker`
---

## 🔒 Threat Vector Insulation & Sandboxing

Cyber Hazard Lab is built from the ground up to guarantee environment containment:
* **Air-Gapped Execution:** Packet processing engines (`Packet`, `TCPPacket`) exist purely as structured Python object instances. The backend handles no raw host socket hooks (`socket.AF_PACKET`), preventing traffic leakage outside the application process.
* **Deterministic Lexical Terminal:** The integrated console uses an isolated token parsing matrix (`if command.startswith("ping")`) rather than exposing input arguments to system execution environments (`os.system` / `subprocess`). The application is natively safe from command injection bypasses.

---

## 🗺️ Roadmap & Development Progress

### 📊 Overview

| Phase | Description | Progress | Status |
| :--- | :---   | :--- | :---: |
| **Phase 1**   | Foundation                        | `███████████████████` 4/4   | ✅ Done |
| **Phase 2**   | Local Networking                  | `███████████████████` 9/9   | ✅ Done |
| **Phase 3**   | Transport Layer                   | `███████████████████` 8/8   | ✅ Done |
| **Phase 4**   | Network Infrastructure            | `███████████████████` 8/8   | ✅ Done |
| **Phase 4.5** | Network Advanced Infrastructure   | `█████░░░░░░░░░░░░░░` 2/8   | 🟡 In Progress |
| **Phase 5**   | Application Layer                 | `███████████████████` 5/5   | ✅ Done |
| **Phase 6**   | Interactive Lab Frontend          | `███████████████████` 16/16 | ✅ Done |
| **Phase 7**   | SOC Integration & Rule Engine     | `███████████████████` 10/10 | ✅ Done |
| **Phase 8**   | Penetrator Dashboard              | `███░░░░░░░░░░░░░░░░` 1/6   | 🟡 In Progress |

*I probably won't implement all of 4.5 soon*
*Also a good chance that I won't be implementing the Penetrator Dashboard because this project took way too long.*
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

#### PHASE 4 — Network Infrastructure ✅
- [x] Router integration
- [x] Routing table engines
- [x] Multiple subnet routing
- [x] ICMP Communication
- [x] Ping Devices
- [x] Traceroute
- [x] Dynamic network topology management
- [x] DNS resolution architecture
Advanced Infrastructure:
- - [x] NAT (Network Address Translation)
- - [x] Wireless Access Points (802.11 AP emulation & coverage radius)
- - [ ] L1 Hub Emulation
- - [ ] State-based Firewall & ACLs
- - [ ] IDS/IPS Node Simulation
- - [ ] Active Directory
- - [ ] LDAP Requests and Printers
- - [ ] Kerberos and SSO


#### PHASE 5 — Application Layer ✅
- [x] Core DNS services
- [x] Secure Shell (SSH) emulation
- [x] Echo Service Integration
- [x] Fully integrated DHCP services (`dhclient`, `dhclient -r`, auto-provisioning scopes)
- [x] HTTP/HTTPS protocol support

#### PHASE 6 — Interactive Lab Frontend ✅
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
- [x] NCM Terminal (Interactive console for devices, e.g. ping, tracert, ipconfig/ifconfig, hostname, netsh, netstat, ss, arp, nslookup, ssh, dhclient, arpspoof, nmap, nc)
- [x] Payload Manager (Manual ICMP/TCP/UDP packet forging)
- [x] Dynamic MAC Learning & Routing Table UI visualization
- [x] PingSweep and TraceRoute and Curl Integration via Validate
- [x] A Complete DNS compatible browser for viewing custom or default endpoints.
- [x] PCAP Export (Download traffic captures for Wireshark)


#### PHASE 7 — SOC Integration & Detection Engine ✅
- [x] Network Telemetry generation & live interface counters (TX/RX packets, uptime)
- [x] Endpoint SIEM Agent (`SIEM_AGENT` RFC 5424 / UDP 514 syslog forwarder)
- [x] SIEM Log Collector daemon (`SIEM_COLLECTOR` high-throughput asynchronous queue)
- [x] Sigma-compatible YAML detection rule engine (`SOCDetectionEngine`)
- [x] Interactive YAML rule creator, validator, and live deployment in SOC Lab UI
- [x] Real-time security alerting framework with cooldown windows & deduplication
- [x] Security operations monitoring dashboard (live overview, event rates, doughnut charts, host posture grid)
- [x] Dynamic host threat posture tracking (`Normal` → `Suspicious` → `Compromised`)
- [x] Incident investigation & alert chaining workflows (MITRE ATT&CK alignment & timeline evidence)
- [x] Full event stream viewer with multi-attribute filtering and metadata inspection

#### PHASE 8 — Penetrator Dashboard ❌
- [x] Dedicated Attacker Endpoint.
- [ ] Active port scanning utilities
- [ ] Host discovery engines
- [ ] Service enumeration
- [ ] Automated network traffic generation
- [ ] Cyber attack simulations



---

