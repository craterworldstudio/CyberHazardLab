"""
SSH Service Implementation for CyberHazardLab.
Provides:
  1. SSHServerDaemon: Receiver service running on TCP Port 22 handling Transport,
     User Authentication Protocol, and Connection Protocol (channel multiplexing & shell exec).
  2. SSHClientDaemon: Sender/Client service initiating connections and executing remote commands.
"""

import time
from .base import ServiceDaemon
from backend.core.event import Event
from backend.protocols.ssh_protocol import (
    SSH_MSG_DISCONNECT,
    SSH_MSG_SERVICE_REQUEST,
    SSH_MSG_SERVICE_ACCEPT,
    SSH_MSG_USERAUTH_REQUEST,
    SSH_MSG_USERAUTH_FAILURE,
    SSH_MSG_USERAUTH_SUCCESS,
    SSH_MSG_CHANNEL_OPEN,
    SSH_MSG_CHANNEL_OPEN_CONFIRMATION,
    SSH_MSG_CHANNEL_OPEN_FAILURE,
    SSH_MSG_CHANNEL_REQUEST,
    SSH_MSG_CHANNEL_SUCCESS,
    SSH_MSG_CHANNEL_FAILURE,
    SSH_MSG_CHANNEL_DATA,
    SSH_MSG_CHANNEL_EOF,
    SSH_MSG_CHANNEL_CLOSE,
    SSH_VERSION_BANNER_SERVER,
    SSH_VERSION_BANNER_CLIENT,
    SSHMessage,
    SSHChannel,
    SSHUserAuthProtocol,
    SSHConnectionProtocol,
)


class SSHServerDaemon(ServiceDaemon):
    """
    SSH Server (Receiver) Daemon.
    Listens on TCP Port 22.
    Implements RFC 4252 (User Authentication) and RFC 4254 (Connection Protocol).
    """

    def __init__(self, host):
        super().__init__(host)
        # Sessions map: (remote_ip, remote_port) -> session state dict
        self.sessions = {}

    def _get_or_create_session(self, session_key):
        if session_key not in self.sessions:
            self.sessions[session_key] = {
                "version_exchanged": False,
                "authenticated": False,
                "user": None,
                "channels": {},
                "next_channel_id": 0
            }
        return self.sessions[session_key]

    def handle_tcp(self, payload, connection, packet):
        if payload is None:
            return None

        session_key = (packet.source_ip, getattr(connection, "remote_port", 0))
        session = self._get_or_create_session(session_key)
        net = getattr(connection, "network", None)

        msg = SSHMessage.decode(str(payload))

        # ----------------------------------------------------------------------
        # 1. Transport Layer: Version Exchange
        # ----------------------------------------------------------------------
        if msg.raw_banner:
            session["version_exchanged"] = True
            if net:
                net.add_event(Event(
                    type="SSH_VERSION_EXCHANGE",
                    severity="INFO",
                    source=packet.source_ip,
                    destination=packet.destination_ip,
                    protocol="SSH",
                    port=22,
                    metadata={
                        "client_version": msg.raw_banner,
                        "server_version": SSH_VERSION_BANNER_SERVER,
                        "host": self.host.name
                    }
                ))
            return f"{SSH_VERSION_BANNER_SERVER}\r\n"

        # ----------------------------------------------------------------------
        # 2. Service Request (ssh-userauth)
        # ----------------------------------------------------------------------
        if msg.msg_type == SSH_MSG_SERVICE_REQUEST:
            service_name = msg.payload.get("service_name", "ssh-userauth")
            if service_name == "ssh-userauth":
                return SSHUserAuthProtocol.create_service_accept(service_name).encode()
            return SSHMessage(msg_type=SSH_MSG_DISCONNECT, payload={"reason": "Service not supported"}).encode()

        # ----------------------------------------------------------------------
        # 3. User Authentication Protocol (RFC 4252)
        # ----------------------------------------------------------------------
        if msg.msg_type == SSH_MSG_USERAUTH_REQUEST:
            username = msg.payload.get("user", "")
            password = msg.payload.get("password", "")
            method = msg.payload.get("method", "password")

            # Get host service config if available
            srv_config = None
            for s in getattr(self.host, "services", []):
                if s.name.upper() in ("SSH", "SSH_SERVER") and s.port == 22:
                    srv_config = getattr(s, "config", {})
                    break

            is_valid = SSHUserAuthProtocol.verify(username, password, srv_config)

            if is_valid:
                session["authenticated"] = True
                session["user"] = username

                if net:
                    net.add_event(Event(
                        type="SSH_AUTH_SUCCESS",
                        severity="INFO",
                        source=packet.source_ip,
                        destination=packet.destination_ip,
                        protocol="SSH",
                        port=22,
                        metadata={
                            "user": username,
                            "method": method,
                            "host": self.host.name
                        }
                    ))
                return SSHUserAuthProtocol.create_userauth_success().encode()
            else:
                session["authenticated"] = False
                if net:
                    net.add_event(Event(
                        type="SSH_AUTH_FAILED",
                        severity="WARNING",
                        source=packet.source_ip,
                        destination=packet.destination_ip,
                        protocol="SSH",
                        port=22,
                        metadata={
                            "user": username,
                            "method": method,
                            "host": self.host.name
                        }
                    ))
                return SSHUserAuthProtocol.create_userauth_failure(["password"]).encode()

        # ----------------------------------------------------------------------
        # 4. Connection Protocol: Channel Open (RFC 4254)
        # ----------------------------------------------------------------------
        if msg.msg_type == SSH_MSG_CHANNEL_OPEN:
            if not session["authenticated"]:
                return SSHMessage(
                    msg_type=SSH_MSG_CHANNEL_OPEN_FAILURE,
                    payload={"reason": "Authentication required"}
                ).encode()

            sender_chan = msg.payload.get("sender_channel", 0)
            server_chan_id = session["next_channel_id"]
            session["next_channel_id"] += 1

            chan = SSHChannel(
                channel_id=server_chan_id,
                recipient_channel=sender_chan,
                channel_type=msg.payload.get("channel_type", "session")
            )
            session["channels"][server_chan_id] = chan

            return SSHConnectionProtocol.create_channel_open_confirmation(
                recipient_channel=sender_chan,
                sender_channel=server_chan_id
            ).encode()

        # ----------------------------------------------------------------------
        # 5. Connection Protocol: Channel Request (exec, pty, shell)
        # ----------------------------------------------------------------------
        if msg.msg_type == SSH_MSG_CHANNEL_REQUEST:
            if not session["authenticated"]:
                return SSHMessage(
                    msg_type=SSH_MSG_CHANNEL_FAILURE,
                    payload={"reason": "Authentication required"}
                ).encode()

            req_type = msg.payload.get("request_type", "exec")
            recipient_chan = msg.payload.get("recipient_channel", 0)

            if req_type == "exec":
                command = msg.payload.get("command", "").strip()
                output = self._execute_host_command(command, session["user"] or "admin")
                
                if net:
                    net.add_event(Event(
                        type="SSH_EXEC_COMMAND",
                        severity="INFO",
                        source=packet.source_ip,
                        destination=packet.destination_ip,
                        protocol="SSH",
                        port=22,
                        metadata={
                            "user": session["user"] or "admin",
                            "command": command,
                            "host": self.host.name
                        }
                    ))

                # Return channel data with output
                return SSHConnectionProtocol.create_channel_data(
                    recipient_channel=recipient_chan,
                    data=output
                ).encode()

            elif req_type in ("shell", "pty-req"):
                return SSHMessage(
                    msg_type=SSH_MSG_CHANNEL_SUCCESS,
                    payload={"recipient_channel": recipient_chan}
                ).encode()

            return SSHMessage(
                msg_type=SSH_MSG_CHANNEL_FAILURE,
                payload={"recipient_channel": recipient_chan}
            ).encode()

        # ----------------------------------------------------------------------
        # 6. Connection Protocol: Channel Data
        # ----------------------------------------------------------------------
        if msg.msg_type == SSH_MSG_CHANNEL_DATA:
            if not session["authenticated"]:
                return None
            recipient_chan = msg.payload.get("recipient_channel", 0)
            data_str = msg.payload.get("data", "").strip()
            if data_str:
                output = self._execute_host_command(data_str, session["user"] or "admin")
                return SSHConnectionProtocol.create_channel_data(
                    recipient_channel=recipient_chan,
                    data=output
                ).encode()
            return None

        # ----------------------------------------------------------------------
        # 7. Connection Protocol: Channel Close
        # ----------------------------------------------------------------------
        if msg.msg_type == SSH_MSG_CHANNEL_CLOSE:
            recipient_chan = msg.payload.get("recipient_channel", 0)
            session["channels"].pop(recipient_chan, None)
            return SSHConnectionProtocol.create_channel_close(recipient_chan).encode()

        # ----------------------------------------------------------------------
        # 8. Legacy / Backwards Compatibility Handling
        # ----------------------------------------------------------------------
        payload_str = str(payload).strip()
        if not session["authenticated"]:
            if "admin" in payload_str and "password" in payload_str:
                session["authenticated"] = True
                session["user"] = "admin"
                if net:
                    net.add_event(Event(
                        type="SSH_AUTH_SUCCESS",
                        severity="INFO",
                        source=packet.source_ip,
                        destination=packet.destination_ip,
                        protocol="SSH",
                        port=22,
                        metadata={"user": "admin", "host": self.host.name}
                    ))
                return f"{SSH_VERSION_BANNER_SERVER}\r\n\r\nAccess Granted. Welcome root.\r\nType commands."
            else:
                if net:
                    net.add_event(Event(
                        type="SSH_AUTH_FAILED",
                        severity="WARNING",
                        source=packet.source_ip,
                        destination=packet.destination_ip,
                        protocol="SSH",
                        port=22,
                        metadata={"payload": payload_str, "host": self.host.name}
                    ))
                return f"{SSH_VERSION_BANNER_SERVER}\r\n\r\nAccess Denied. Invalid credentials."
        else:
            output = self._execute_host_command(payload_str, session["user"] or "admin")
            return f"{session['user'] or 'admin'}@{self.host.name}:~$ {payload_str}\r\n{output}"

    def _execute_host_command(self, command: str, username: str) -> str:
        """Executes a command locally on the target host using TerminalCommandHandler."""
        try:
            from application.term_coms import TerminalCommandHandler
            sim = getattr(self.host.network, "orchestrator", None)
            handler = TerminalCommandHandler(sim=sim)
            return handler.execute(self.host, command)
        except Exception as e:
            return f"SSH_EXEC_ERROR: {str(e)}"


class SSHClientDaemon(ServiceDaemon):
    """
    SSH Client (Sender) Daemon.
    Provides client-side capabilities to initiate SSH sessions,
    authenticate with remote SSH servers, and execute remote commands.
    """

    def __init__(self, host):
        super().__init__(host)
        self.active_sessions = {}

    def execute_remote(
        self,
        remote_ip: str,
        command: str = "",
        username: str = "admin",
        password: str = "password",
        port: int = 22,
        timeout: float = 1.0
    ) -> dict:
        """
        Executes an end-to-end SSH client interaction with the target host:
          1. TCP connect & SSH version exchange
          2. SSH Service Request & User Authentication Protocol
          3. SSH Connection Protocol channel open & command execution
        """
        if not self.host or not getattr(self.host, "network", None):
            return {"success": False, "error": "Client device is not attached to a network."}

        network = self.host.network
        sim = getattr(network, "orchestrator", None)

        # 1. Lookup route to destination
        route, intf = network.get_route(self.host, remote_ip)
        if not route or not intf:
            return {"success": False, "error": f"Network unreachable: No route to {remote_ip}"}

        # 2. Lookup destination device & verify SSH service
        dest_host = network.get_host_by_ip(remote_ip)
        if not dest_host:
            return {"success": False, "error": f"No device responded at {remote_ip}"}

        ssh_server = None
        for s in getattr(dest_host, "services", []):
            if s.protocol.upper() == "TCP" and s.port == port and s.status.lower() == "running":
                ssh_server = s
                break

        if not ssh_server:
            if network:
                network.add_event(Event(
                    type="SSH_CONNECTION_REFUSED",
                    severity="WARNING",
                    source=f"{intf.ip}:50000",
                    destination=f"{remote_ip}:{port}",
                    protocol="TCP",
                    metadata={"reason": "Port closed / SSH service not running"}
                ))
            return {"success": False, "error": f"Connection refused: Port {port} is closed on {remote_ip}."}

        # 3. Step 1: Version Exchange
        server_daemon = dest_host.get_service_daemon(ssh_server.name)
        banner_packet = type("MockPacket", (), {
            "source_ip": intf.ip,
            "destination_ip": remote_ip
        })()
        
        from backend.network.tcp import TCPConnection, TCPState
        mock_conn = TCPConnection(
            local_ip=remote_ip,
            local_port=port,
            remote_ip=intf.ip,
            remote_port=50000,
            network=network
        )
        mock_conn.state = TCPState.ESTABLISHED

        # Send client banner
        server_banner = server_daemon.handle_tcp(SSH_VERSION_BANNER_CLIENT, mock_conn, banner_packet)
        if not server_banner or not server_banner.startswith("SSH-2.0-"):
            return {"success": False, "error": "SSH version exchange failed."}

        # 4. Step 2: Service Request (ssh-userauth)
        svc_req = SSHUserAuthProtocol.create_service_request("ssh-userauth")
        svc_accept_raw = server_daemon.handle_tcp(svc_req.encode(), mock_conn, banner_packet)
        svc_accept = SSHMessage.decode(svc_accept_raw)
        if svc_accept.msg_type != SSH_MSG_SERVICE_ACCEPT:
            return {"success": False, "error": "SSH service request for ssh-userauth rejected."}

        # 5. Step 3: User Authentication Protocol
        auth_req = SSHUserAuthProtocol.create_userauth_request(username, password)
        auth_resp_raw = server_daemon.handle_tcp(auth_req.encode(), mock_conn, banner_packet)
        auth_resp = SSHMessage.decode(auth_resp_raw)

        if auth_resp.msg_type != SSH_MSG_USERAUTH_SUCCESS:
            return {
                "success": False,
                "error": f"Permission denied, please try again (password). Authentication failed for user '{username}'.",
                "auth_failed": True
            }

        # 6. Step 4: Connection Protocol - Open Channel
        chan_open = SSHConnectionProtocol.create_channel_open(sender_channel=0)
        chan_conf_raw = server_daemon.handle_tcp(chan_open.encode(), mock_conn, banner_packet)
        chan_conf = SSHMessage.decode(chan_conf_raw)

        if chan_conf.msg_type != SSH_MSG_CHANNEL_OPEN_CONFIRMATION:
            return {"success": False, "error": "Failed to open SSH session channel."}

        server_chan_id = chan_conf.payload.get("sender_channel", 0)

        # 7. Step 5: Connection Protocol - Execute Command or Open Shell
        if command:
            cmd_req = SSHConnectionProtocol.create_channel_request(
                recipient_channel=server_chan_id,
                request_type="exec",
                command=command
            )
            cmd_resp_raw = server_daemon.handle_tcp(cmd_req.encode(), mock_conn, banner_packet)
            cmd_resp = SSHMessage.decode(cmd_resp_raw)

            output = cmd_resp.payload.get("data", "")
            return {
                "success": True,
                "output": output,
                "user": username,
                "remote_ip": remote_ip,
                "server_version": server_banner.strip()
            }
        else:
            # Interactive shell welcome banner
            return {
                "success": True,
                "output": (
                    f"Connected to {remote_ip} ({server_banner.strip()}).\n"
                    f"{username}@{remote_ip}'s password: (authenticated)\n"
                    f"Welcome to Nox OS on {dest_host.name}!\n"
                    f"Use 'ssh {username}@{remote_ip} <command>' to execute remote commands."
                ),
                "user": username,
                "remote_ip": remote_ip,
                "interactive": True
            }
