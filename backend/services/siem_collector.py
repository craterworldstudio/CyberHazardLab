import time
import json
import uuid
import queue
import threading
from .base import ServiceDaemon
from backend.core.event import Event
from .soc_engine import DEFAULT_YAML_RULES, SOCDetectionEngine


# Kept for backward compatibility with existing imports
DEFAULT_SOC_RULES = [
    {
        "id": "rule-ssh-brute-force",
        "name": "SSH Brute Force Attack",
        "severity": "CRITICAL",
        "condition": "event.type == 'SSH_AUTH_FAILED'",
        "description": "3 or more SSH authentication failures from the same source within 60 seconds."
    },
    {
        "id": "rule-root-login",
        "name": "Direct Root Login / Privilege Escalation",
        "severity": "CRITICAL",
        "condition": "user == 'root' and (event.type in ['SSH_AUTH_SUCCESS', 'ROOT_LOGIN'] or 'sudo' in command)",
        "description": "Direct root user interactive session or superuser privilege escalation detected."
    },
    {
        "id": "rule-ssh-success",
        "name": "SSH Interactive Login",
        "severity": "LOW",
        "condition": "event.type == 'SSH_AUTH_SUCCESS'",
        "description": "Successful remote SSH authentication and interactive session opened."
    },
    {
        "id": "rule-icmp-sweep",
        "name": "ICMP Reconnaissance Sweep",
        "severity": "MEDIUM",
        "condition": "protocol == 'ICMP'",
        "description": "ICMP echo requests targeting 4 or more distinct destination IPs within 15 seconds."
    },
    {
        "id": "rule-port-scan",
        "name": "Network Port Scanning",
        "severity": "HIGH",
        "condition": "command.contains('nmap') or protocol in ['TCP', 'SYN']",
        "description": "Port scanning tool execution or multiple connection probes across distinct ports."
    },
    {
        "id": "rule-arp-spoof",
        "name": "ARP Cache Poisoning / MITM",
        "severity": "CRITICAL",
        "condition": "command.contains('arpspoof') or conflict == true",
        "description": "ARP spoofing tool execution or conflicting IP-to-MAC reply indicates active poisoning."
    },
    {
        "id": "rule-reverse-shell",
        "name": "Interactive Reverse Shell Execution",
        "severity": "CRITICAL",
        "condition": "command.contains('nc') and command.contains('-e')",
        "description": "Inbound or outbound TCP netcat connection redirected to an interactive shell."
    }
]


class SIEMCollectorDaemon(ServiceDaemon):
    """
    Central SIEM Collector Daemon.
    Responsible for high-throughput, non-blocking ingestion of forwarded logs,
    syslog UDP 514 datagrams, and simulation telemetry. Buffers and stores events,
    then forwards them to the SOC Lab Detection Engine for rule evaluation.
    """

    def __init__(self, host):
        super().__init__(host)
        self.is_running = False
        self.service_model = None
        self.port = 514
        self.ingested_events = []
        self.max_events = 1000
        self.total_events_count = 0
        self._seen_event_ids = set()
        self._queue = queue.Queue(maxsize=10000)
        self._worker_thread = None

    def on_start(self, service_model):
        self.is_running = True
        self.service_model = service_model
        cfg = getattr(service_model, "config", {}) or {}
        self.port = int(cfg.get("port", 514))

        # Sync with simulation soc_state and initialize SOC detection engine
        sim = getattr(getattr(self.host, "network", None), "orchestrator", None)
        if sim:
            if not hasattr(sim, "soc_state") or not isinstance(sim.soc_state, dict):
                sim.soc_state = {}

            sim.soc_state.setdefault("alerts", [])
            sim.soc_state.setdefault("incidents", [])
            sim.soc_state.setdefault("ingested_events", [])
            sim.soc_state.setdefault("total_events_count", len(sim.soc_state["ingested_events"]))

            self.ingested_events = sim.soc_state["ingested_events"]
            self.total_events_count = sim.soc_state.get("total_events_count", len(self.ingested_events))

            # Initialize SOC Detection Engine on simulation
            if not getattr(sim, "soc_engine", None):
                sim.soc_engine = SOCDetectionEngine(sim)

            # Fast registration for simulation network
            if hasattr(sim, "network"):
                sim.network._soc_collector = self

        # Launch background worker thread for asynchronous log ingestion
        if not self._worker_thread or not self._worker_thread.is_alive():
            self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True, name="SIEM-Collector-Worker")
            self._worker_thread.start()

    def on_stop(self, service_model):
        self.is_running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass

    def ingest_event(self, event_data: dict):
        """Non-blocking ingestion hook. Pushes event onto background queue without stalling simulation."""
        if not self.is_running or not event_data:
            return

        ev_id = event_data.get("id")
        if ev_id and ev_id in self._seen_event_ids:
            return
        if ev_id:
            self._seen_event_ids.add(ev_id)
            if len(self._seen_event_ids) > 2000:
                self._seen_event_ids.clear()

        try:
            self._queue.put_nowait(event_data)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(event_data)
            except Exception:
                pass

    def _worker_loop(self):
        """Background thread continuously processing queued events, buffering, and dispatching to SOC engine."""
        while self.is_running:
            try:
                event_data = self._queue.get(timeout=0.1)
                if event_data is None:
                    break
            except queue.Empty:
                continue
            except Exception:
                continue

            try:
                self._process_event(event_data)
            except Exception:
                pass

    def _process_event(self, event_data: dict):
        """Buffers event and delegates rule detection to the SOC Lab Detection Engine."""
        # 1. Update lifetime count and in-memory buffer
        self.total_events_count += 1
        self.ingested_events.append(event_data)
        if len(self.ingested_events) > self.max_events:
            self.ingested_events.pop(0)

        sim = getattr(getattr(self.host, "network", None), "orchestrator", None)
        if sim and hasattr(sim, "soc_state"):
            sim.soc_state["ingested_events"] = self.ingested_events
            sim.soc_state["total_events_count"] = self.total_events_count

            # 2. Forward to SOC Lab Detection Engine for rule matching & alerting
            soc_engine = getattr(sim, "soc_engine", None)
            if not soc_engine:
                sim.soc_engine = SOCDetectionEngine(sim)
                soc_engine = sim.soc_engine

            if soc_engine:
                soc_engine.process_event(event_data)

    def handle_udp(self, payload, connection, packet):
        """Processes incoming syslog / JSON datagrams received on port 514."""
        if not self.is_running:
            return None

        raw_str = str(payload).strip()
        if not raw_str:
            return None

        event_data = self._parse_payload(raw_str, packet)
        if not event_data:
            return None

        self.ingest_event(event_data)

        # Syslog over UDP is unidirectional (fire-and-forget); no reverse packet
        return None

    def _parse_payload(self, raw_str: str, packet) -> dict:
        """Parses JSON or syslog text into a standard event dictionary."""
        try:
            if raw_str.startswith("{") and raw_str.endswith("}"):
                data = json.loads(raw_str)
                data.setdefault("id", f"ev-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}")
                data.setdefault("received_from", packet.source_ip if packet else "unknown")
                return data
        except Exception:
            pass

        # Fallback to plain syslog line parsing
        return {
            "id": f"ev-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "host": getattr(packet, "source_ip", "unknown"),
            "type": "SYSLOG_LINE",
            "severity": "INFO",
            "source": packet.source_ip if packet else "unknown",
            "destination": self.host.name,
            "protocol": "UDP",
            "message": raw_str,
            "metadata": {"raw": raw_str}
        }
