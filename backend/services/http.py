from .base import ServiceDaemon

class HTTPServerDaemon(ServiceDaemon):
    def __init__(self, host):
        super().__init__(host)
        # Virtual filesystem for the web server
        self.vfs = {
            "/": "<html><body><h1>Welcome to CS50 SOC Lab!</h1><p>Running CS50 HttpDaemon v1.0</p></body></html>",
            "/login": "<html><body><form><input type='text' name='user'/><input type='password' name='pass'/><input type='submit'/></form></body></html>",
            "/api/health": '{"status": "ok", "version": "1.0"}'
        }

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
            return "HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nFATAL: SQL Injection Detected! Database connection dropped."
            
        parts = request_line.split()
        if len(parts) >= 2 and parts[0] in ("GET", "POST"):
            method = parts[0]
            path = parts[1]
            
            if path in self.vfs:
                content = self.vfs[path]
                return f"HTTP/1.1 200 OK\r\nContent-Length: {len(content)}\r\nContent-Type: text/html\r\n\r\n{content}"
            else:
                return "HTTP/1.1 404 Not Found\r\n\r\n404 - Page not found."
                
        return "HTTP/1.1 400 Bad Request\r\n\r\nInvalid HTTP Request."
