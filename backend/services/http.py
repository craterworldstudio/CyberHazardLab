from .base import ServiceDaemon

class HTTPServerDaemon(ServiceDaemon):
    def __init__(self, host):
        super().__init__(host)
        # Virtual filesystem for the web server
        self.vfs = {
            "/health": '{"status": "ok", "version": "1.0"}',
            "/ready": '{"status": "ready"}',
            "/live": '{"status": "alive"}',
            "/metrics": '{"requests": 100, "errors": 0}'
        }

    def reload_config(self, config):
        if config and "endpoints" in config:
            self.vfs = config["endpoints"]

    def on_start(self, service_model):
        if hasattr(service_model, "config") and service_model.config:
            if "endpoints" in service_model.config:
                self.vfs = service_model.config["endpoints"]

    def handle_tcp(self, payload, connection, packet):
        payload_str = str(payload).strip()
        if not payload_str:
            return None
            
        lines = payload_str.split("\n")
        request_line = lines[0].strip()
        
        # Simple SQL Injection detection
        upper_payload = payload_str.upper()
        if "DROP TABLE" in upper_payload or "OR 1=1" in upper_payload or "UNION SELECT" in upper_payload or "';--" in upper_payload:
            if connection.network:
                from backend.core.event import Event
                connection.network.add_event(Event(
                    type="SQL_INJECTION_DETECTED",
                    severity="HIGH",
                    source=packet.source_ip,
                    destination=packet.destination_ip,
                    protocol="HTTP",
                    metadata={"payload": request_line, "host": self.host.name}
                ))
            return "HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/html\r\n\r\n<!DOCTYPE html><html><head><title>500 Internal Error</title><style>body{background:#080c10;color:#ff5555;font-family:monospace;padding:40px;margin:0;}h1{color:#ff5555;text-shadow:0 0 10px #ff0055;}a{color:#00e5ff;}</style></head><body><h1>500 // INTERNAL SERVER ERROR</h1><p>FATAL: SQL Injection Detected! Database connection dropped.</p><p><a href=\"/\">&lt; Return to Safety</a></p></body></html>"
            
        parts = request_line.split()
        if len(parts) >= 2 and parts[0] in ("GET", "POST"):
            method = parts[0]
            raw_path = parts[1]
            clean_path = raw_path.split("?")[0] if "?" in raw_path else raw_path
            
            if clean_path in self.vfs:
                content = self.vfs[clean_path]
                return f"HTTP/1.1 200 OK\r\nContent-Length: {len(content)}\r\nContent-Type: text/html\r\n\r\n{content}"
            elif raw_path in self.vfs:
                content = self.vfs[raw_path]
                return f"HTTP/1.1 200 OK\r\nContent-Length: {len(content)}\r\nContent-Type: text/html\r\n\r\n{content}"
            else:
                not_found_html = f"<!DOCTYPE html><html><head><title>404 Not Found</title><style>body{{background:#080c10;color:#ff5555;font-family:monospace;padding:40px;margin:0;}}h1{{color:#ff5555;text-shadow:0 0 10px #ff0055;}}a{{color:#00e5ff;}}</style></head><body><h1>404 // OBJECT NOT FOUND</h1><p>The requested endpoint '{clean_path}' does not exist on this server.</p><p><a href=\"/\">&lt; Return to Home</a></p></body></html>"
                return f"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\nContent-Length: {len(not_found_html)}\r\n\r\n{not_found_html}"
                
        return "HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n<!DOCTYPE html><html><head><title>400 Bad Request</title><style>body{background:#080c10;color:#ffaa00;font-family:monospace;padding:40px;margin:0;}</style></head><body><h1>400 // BAD REQUEST</h1><p>Invalid HTTP Request.</p></body></html>"
