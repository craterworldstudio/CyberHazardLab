import time
import json
from .base import ServiceDaemon
from backend.network.packet import Packet, UDPPacket
from backend.core.event import Event


class SIEMAgentDaemon(ServiceDaemon):
    """
    Endpoint SIEM Agent.
    Monitors local host events and tails VFS log files (/var/log/auth.log,
    /var/log/kern.log, /var/log/syslog, /var/log/nginx/access.log),
    packaging and forwarding them to the central SIEM Collector via UDP port 514.
    """

    def __init__(self, host):
        super().__init__(host)
        self.is_running = False
        self.service_model = None
        self.collector_ip = None
        self.collector_port = 514
        self.transport = "UDP"
        self.file_offsets = {}
        self.forwarded_count = 0
        self.last_tail_time = 0
        self._sending = False

    def on_start(self, service_model):
        self.is_running = True
        self.service_model = service_model
        cfg = getattr(service_model, "config", {}) or {}
        self.reload_config(cfg)
        
        # Log agent startup to local syslog
        if hasattr(self.host, "log_event"):
            self.host.log_event(Event(
                type="SIEM_AGENT_STARTED",
                severity="INFO",
                source=self.host.name,
                destination=self.collector_ip or "broadcast",
                protocol="UDP",
                metadata={"collector_ip": self.collector_ip, "port": self.collector_port}
            ))

    def on_stop(self, service_model):
        self.is_running = False

    def reload_config(self, cfg: dict):
        self.collector_ip = cfg.get("collector_ip")
        self.collector_port = int(cfg.get("port", 514))
        self.transport = cfg.get("transport", "UDP")

        # Auto-discover collector IP if not specified in config or if target lacks a collector
        discovered = self._discover_collector_ip()
        if not self.collector_ip and discovered:
            self.collector_ip = discovered
        elif self.collector_ip and discovered and self.collector_ip != discovered:
            network = getattr(self.host, "network", None)
            sim = getattr(network, "orchestrator", None) if network else None
            if sim:
                has_collector = any(
                    any(s.name.upper() in ("SIEM_COLLECTOR", "SIEM-COLLECTOR", "SIEM") and getattr(s, "status", "").upper() == "RUNNING" for s in getattr(dev, "services", []))
                    for dev in list(sim.hosts.values()) + list(sim.routers.values())
                    if dev.interfaces and any(i.ip == self.collector_ip for i in dev.interfaces)
                )
                if not has_collector:
                    self.collector_ip = discovered

    def _discover_collector_ip(self):
        """Looks for any host in the network running the SIEM_COLLECTOR service."""
        network = getattr(self.host, "network", None)
        if not network:
            return None
        sim = getattr(network, "orchestrator", None)
        if not sim:
            return None
        for dev in list(sim.hosts.values()) + list(sim.routers.values()):
            for s in getattr(dev, "services", []):
                if s.name.upper() in ("SIEM_COLLECTOR", "SIEM-COLLECTOR", "SIEM") and getattr(s, "status", "").upper() == "RUNNING":
                    if dev.interfaces and dev.interfaces[0].ip:
                        return dev.interfaces[0].ip
        return None

    def forward_event(self, event):
        """Called whenever an event is logged on this host to immediately stream it."""
        if not self.is_running or self._sending:
            return

        ev_type = getattr(event, "type", "EVENT")
        ev_port = getattr(event, "port", None)

        # Do NOT forward low-level link layer frame events, packet routing events, internal SIEM agent events, or SIEM UDP transport events
        if (
            ev_type in (
                "FRAME_RECEIVED", "FRAME_FORWARDED", "FRAME_SENT",
                "PACKET_RECEIVED", "PACKET_FORWARDED", "PACKET_SENT", "PACKET_ROUTED"
            )
            or ev_port in (514, 51400)
            or ev_type.startswith("SIEM_")
        ):
            return

        if not self.collector_ip:
            self.collector_ip = self._discover_collector_ip()
            if not self.collector_ip:
                return

        payload_dict = {
            "version": "1.0",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "host": self.host.name,
            "type": ev_type,
            "severity": getattr(event, "severity", "INFO"),
            "source": getattr(event, "source", self.host.name),
            "destination": getattr(event, "destination", ""),
            "protocol": getattr(event, "protocol", "SYS"),
            "port": ev_port,
            "metadata": getattr(event, "metadata", {}) or {}
        }
        raw_msg = json.dumps(payload_dict)
        self._send_to_collector(raw_msg)

    def tail_and_forward(self):
        """Checks VFS logs for new content and forwards newly appended lines."""
        if not self.is_running or not hasattr(self.host, "vfs"):
            return
        if not self.collector_ip:
            self.collector_ip = self._discover_collector_ip()
            if not self.collector_ip:
                return

        vfs = self.host.vfs
        logs_to_check = [
            "/var/log/auth.log",
            "/var/log/kern.log",
            "/var/log/nginx/access.log",
            "/var/log/syslog"
        ]

        for log_path in logs_to_check:
            node = vfs.path_to_tree(log_path)
            if node and hasattr(node, "contents") and node.contents:
                content = str(node.contents)
                offset = self.file_offsets.get(log_path, 0)
                if len(content) > offset:
                    new_slice = content[offset:]
                    self.file_offsets[log_path] = len(content)
                    for line in new_slice.splitlines():
                        line = line.strip()
                        if line:
                            msg = json.dumps({
                                "version": "1.0",
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "host": self.host.name,
                                "type": "LOG_ENTRY",
                                "severity": "INFO",
                                "log_file": log_path,
                                "message": line,
                                "source": self.host.name,
                                "metadata": {"file": log_path}
                            })
                            self._send_to_collector(msg)

    def _send_to_collector(self, payload_str: str):
        """Dispatches UDP syslog packet to the collector."""
        if self._sending or not self.host.interfaces:
            return
        intf = self.host.interfaces[0]
        if not intf.ip or intf.ip in ("0.0.0.0", "") or getattr(intf, "status", "up") != "up":
            return

        udp_pkt = UDPPacket(
            source_port=51400,
            destination_port=self.collector_port,
            payload=payload_str
        )
        packet = Packet(
            source_ip=intf.ip,
            destination_ip=self.collector_ip,
            protocol="UDP",
            payload=udp_pkt
        )
        self._sending = True
        try:
            self.host.send_ip_packet(packet, out_interface=intf)
            self.forwarded_count += 1
        except Exception:
            pass
        finally:
            self._sending = False
