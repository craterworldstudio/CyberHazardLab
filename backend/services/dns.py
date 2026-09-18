from .base import ServiceDaemon
import traceback

class DNSServerDaemon(ServiceDaemon):
    def handle_udp(self, payload, connection, packet):
        payload_str = str(payload).strip()
        
        if not payload_str:
            return None
            
        try:
            network = connection.network
            
            # Simple simulation: just loop through all hosts and routers and resolve by name
            target_name = payload_str.upper()
            
            # Special case for wildcard or if it contains a protocol like "GET"
            if target_name.startswith("GET ") or target_name.startswith("POST "):
                return "DNS_ERROR: Invalid query."
                
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
