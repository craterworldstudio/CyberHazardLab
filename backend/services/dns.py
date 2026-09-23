from .base import ServiceDaemon
import traceback

class DNSServerDaemon(ServiceDaemon):
    def handle_udp(self, payload, connection, packet):
        payload_str = str(payload).strip()
        
        if not payload_str:
            return None
            
        try:
            target_name = payload_str.upper()
            
            if target_name.startswith("GET ") or target_name.startswith("POST "):
                return "DNS_ERROR: Invalid query."
                
            if hasattr(self, 'config') and 'records' in self.config:
                records = self.config['records']
                
                # New format: List of dicts [{"name": "...", "type": "A", "target": "..."}]
                if isinstance(records, list):
                    for rec in records:
                        # For now, we natively resolve everything to its target for simplicity in the simulation
                        if isinstance(rec, dict) and rec.get('name', '').strip().upper() == target_name:
                            return f"DNS_RESPONSE: {payload_str} -> {rec.get('target', '').strip()}"
                            
                # Legacy formats
                elif isinstance(records, str):
                    for line in records.split('\n'):
                        line = line.strip()
                        if not line or '=' not in line: continue
                        host, ip = line.split('=', 1)
                        if host.strip().upper() == target_name:
                            return f"DNS_RESPONSE: {payload_str} -> {ip.strip()}"
                elif isinstance(records, dict):
                    for host, ip in records.items():
                        if host.upper() == target_name:
                            return f"DNS_RESPONSE: {payload_str} -> {ip}"
                            
            network = connection.network
            all_devices = list(network.orchestrator.hosts.values()) + list(network.orchestrator.routers.values())
            
            for dev in all_devices:
                if dev.name.upper() == target_name:
                    ip = getattr(dev, "get_ip", lambda: None)()
                    if not ip and dev.interfaces:
                        ip = dev.interfaces[0].ip
                    if ip:
                        return f"DNS_RESPONSE: {payload_str} -> {ip}"
                        
            return f"DNS_NXDOMAIN: '{payload_str}' not found."
            
        except Exception as e:
            traceback.print_exc()
            return f"DNS_ERROR: {str(e)}"
            
        return None
