import threading
import traceback
from .base import ServiceDaemon


class DNSServerDaemon(ServiceDaemon):

    def _get_config(self):
        # 1. From active service model on the host
        if hasattr(self.host, "services"):
            for s in self.host.services:
                if s.name.upper() in ("DNS", "DNS_SERVER") and getattr(s, "config", None):
                    return s.config
        # 2. From saved _service_model reference
        if hasattr(self, "_service_model") and getattr(self._service_model, "config", None):
            return self._service_model.config
        # 3. Fallback to self.config
        return getattr(self, "config", {}) or {}

    def on_start(self, service_model):
        """Kick off the health-check loop when the service starts."""
        self._service_model = service_model
        self._stop_event = threading.Event()
        self._schedule_health_check(delay=1)

    def on_stop(self, service_model):
        """Cancel any pending health-check timer."""
        if hasattr(self, '_stop_event'):
            self._stop_event.set()
        if hasattr(self, '_health_timer') and self._health_timer is not None:
            self._health_timer.cancel()
            self._health_timer = None

    def reload_config(self, cfg):
        """Called when config is saved. Reschedule health check immediately."""
        self.config = cfg
        if hasattr(self, '_stop_event') and not self._stop_event.is_set():
            if hasattr(self, '_health_timer') and self._health_timer is not None:
                self._health_timer.cancel()
            self._schedule_health_check(delay=1)

    def _schedule_health_check(self, delay=None):
        if hasattr(self, '_stop_event') and self._stop_event.is_set():
            return
        cfg = self._get_config()
        interval = float(cfg.get('health_interval', 30))
        if delay is None:
            delay = interval
        self._health_timer = threading.Timer(delay, self._run_health_check)
        self._health_timer.daemon = True
        self._health_timer.start()

    def _run_health_check(self):
        if hasattr(self, '_stop_event') and self._stop_event.is_set():
            return
        try:
            cfg = self._get_config()
            records = cfg.get('records', [])
            network = getattr(self.host, 'network', None)
            orchestrator = getattr(network, 'orchestrator', None)

            for rec in records:
                if not isinstance(rec, dict):
                    continue
                target = rec.get('target', '').strip()
                if not target:
                    rec['status'] = 'OFFLINE'
                    continue

                reachable = False
                if orchestrator and hasattr(orchestrator, 'ping'):
                    try:
                        resolved_target = self._resolve(target.upper(), network) if rec.get('type', 'A').upper() == 'CNAME' else target
                        if not resolved_target:
                            resolved_target = target
                        result = orchestrator.ping(self.host, resolved_target, payload='dns_health', ttl=64)
                        # result is dict with {"type": "ECHO_REPLY", ...} or None
                        if isinstance(result, dict) and result.get("type") == "ECHO_REPLY":
                            reachable = True
                        elif result is not None and 'SUCCESS' in str(result).upper():
                            reachable = True
                    except Exception:
                        reachable = False

                if not reachable and orchestrator:
                    # Secondary reachability check: check if any device interface has this target IP
                    all_devs = (list(getattr(orchestrator, 'hosts', {}).values()) +
                                list(getattr(orchestrator, 'routers', {}).values()))
                    for dev in all_devs:
                        for intf in getattr(dev, 'interfaces', []):
                            if getattr(intf, 'ip', None) == target:
                                reachable = True
                                break
                        if reachable:
                            break

                rec['status'] = 'ONLINE' if reachable else 'UNRESPONSIVE'
        except Exception:
            traceback.print_exc()
        finally:
            # Re-schedule for the next interval
            self._schedule_health_check()

    def _resolve(self, query: str, network, depth=0) -> str:
        if depth > 10:
            return None # Prevent infinite loop
        
        cfg = self._get_config()
        if 'records' in cfg:
            records = cfg['records']
            if isinstance(records, list):
                for rec in records:
                    if isinstance(rec, dict) and rec.get('name', '').strip().upper() == query:
                        rtype = rec.get('type', 'A').upper()
                        target = rec.get('target', '').strip()
                        if rtype == 'CNAME':
                            return self._resolve(target.upper(), network, depth + 1)
                        return target
            elif isinstance(records, str):
                for line in records.split('\n'):
                    line = line.strip()
                    if line and '=' in line:
                        host, ip = line.split('=', 1)
                        if host.strip().upper() == query:
                            return ip.strip()
            elif isinstance(records, dict):
                for host, ip in records.items():
                    if host.upper() == query:
                        return ip

        # Fallback to device names
        all_devices = list(network.orchestrator.hosts.values()) + list(network.orchestrator.routers.values())
        for dev in all_devices:
            if dev.name.upper() == query:
                ip = getattr(dev, "get_ip", lambda: None)()
                if not ip and dev.interfaces:
                    ip = dev.interfaces[0].ip
                if ip:
                    return ip

        if query == "DNS.GOOGLE":
            for intf in getattr(self.host, "interfaces", []):
                if getattr(intf, "ip", "") == "8.8.8.8":
                    return "8.8.8.8"

        return None

    def handle_udp(self, payload, connection, packet):
        payload_str = str(payload).strip()
        if not payload_str:
            return None

        try:
            target_name = payload_str.upper()

            if target_name.startswith("GET ") or target_name.startswith("POST "):
                return "DNS_ERROR: Invalid query."

            network = connection.network
            resolved_ip = self._resolve(target_name, network)
            
            if resolved_ip:
                return f"DNS_RESPONSE: {payload_str} -> {resolved_ip}"
            
            return f"DNS_NXDOMAIN: '{payload_str}' not found."

        except Exception as e:
            traceback.print_exc()
            return f"DNS_ERROR: {str(e)}"

        return None
