from .base import ServiceDaemon

class SSHServerDaemon(ServiceDaemon):
    def __init__(self, host):
        super().__init__(host)
        # Dictionary to track connection state by remote IP and Port
        # key: (remote_ip, remote_port) -> value: {"authenticated": bool}
        self.sessions = {}

    def handle_tcp(self, payload, connection, packet):
        payload_str = str(payload).strip()
        if not payload_str:
            return None
            
        session_key = (packet.source_ip, connection.remote_port)
        
        if session_key not in self.sessions:
            self.sessions[session_key] = {"authenticated": False}
            
        session = self.sessions[session_key]
        
        if not session["authenticated"]:
            # Check for credentials in the payload
            # Extremely rudimentary authentication simulation
            if "admin" in payload_str and "password" in payload_str:
                session["authenticated"] = True
                
                if connection.network:
                    from backend.core.event import Event
                    connection.network.add_event(Event(
                        type="SSH_AUTH_SUCCESS",
                        severity="INFO",
                        source=packet.source_ip,
                        destination=packet.destination_ip,
                        protocol="SSH",
                        metadata={"user": "admin", "host": self.host.name}
                    ))
                return "SSH-2.0-OpenSSH_8.2p1 Ubuntu\r\n\r\nAccess Granted. Welcome root.\r\nType commands (e.g., 'ip addr show', 'ping 10.0.1.1')."
            else:
                if connection.network:
                    from backend.core.event import Event
                    connection.network.add_event(Event(
                        type="SSH_AUTH_FAILED",
                        severity="WARNING",
                        source=packet.source_ip,
                        destination=packet.destination_ip,
                        protocol="SSH",
                        metadata={"payload": payload_str, "host": self.host.name}
                    ))
                return "SSH-2.0-OpenSSH_8.2p1 Ubuntu\r\n\r\nAccess Denied. Invalid credentials."
                
        else:
            # User is authenticated, parse as a command
            # We import the TerminalCommandHandler
            try:
                from application.term_coms import TerminalCommandHandler
                
                sim = connection.network.orchestrator
                handler = TerminalCommandHandler(sim=sim)
                
                output = handler.execute(self.host, payload_str)
                return f"admin@{self.host.name}:~$ {payload_str}\r\n{output}"
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return f"SSH_SHELL_ERROR: {str(e)}"
