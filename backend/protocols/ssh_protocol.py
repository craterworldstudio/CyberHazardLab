"""
SSH Protocol Suite Implementation for CyberHazardLab.
Implements:
  1. SSH Transport Layer Protocol (RFC 4253) - Version exchange & packet framing
  2. SSH User Authentication Protocol (RFC 4252) - Userauth requests & validation
  3. SSH Connection Protocol (RFC 4254) - Channel multiplexing & command execution
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional

# ==============================================================================
# SSH Message Numbers (RFC 4250 / RFC 4251 / RFC 4252 / RFC 4254)
# ==============================================================================

# Transport Layer Numbers
SSH_MSG_DISCONNECT = 1
SSH_MSG_IGNORE = 2
SSH_MSG_UNIMPLEMENTED = 3
SSH_MSG_DEBUG = 4
SSH_MSG_SERVICE_REQUEST = 5
SSH_MSG_SERVICE_ACCEPT = 6

# User Authentication Numbers
SSH_MSG_USERAUTH_REQUEST = 50
SSH_MSG_USERAUTH_FAILURE = 51
SSH_MSG_USERAUTH_SUCCESS = 52
SSH_MSG_USERAUTH_BANNER = 53

# Connection Protocol Numbers
SSH_MSG_GLOBAL_REQUEST = 80
SSH_MSG_REQUEST_SUCCESS = 81
SSH_MSG_REQUEST_FAILURE = 82
SSH_MSG_CHANNEL_OPEN = 90
SSH_MSG_CHANNEL_OPEN_CONFIRMATION = 91
SSH_MSG_CHANNEL_OPEN_FAILURE = 92
SSH_MSG_CHANNEL_WINDOW_ADJUST = 93
SSH_MSG_CHANNEL_DATA = 94
SSH_MSG_CHANNEL_EXTENDED_DATA = 95
SSH_MSG_CHANNEL_EOF = 96
SSH_MSG_CHANNEL_CLOSE = 97
SSH_MSG_CHANNEL_REQUEST = 98
SSH_MSG_CHANNEL_SUCCESS = 99
SSH_MSG_CHANNEL_FAILURE = 100

# Protocol Version Banner
SSH_VERSION_BANNER_SERVER = "SSH-2.0-CyberHazardLab_SSH_Server_1.0"
SSH_VERSION_BANNER_CLIENT = "SSH-2.0-CyberHazardLab_SSH_Client_1.0"


# ==============================================================================
# SSH Message Framing & Serialization
# ==============================================================================

@dataclass
class SSHMessage:
    """Represents an SSH protocol message."""
    msg_type: int
    payload: dict = field(default_factory=dict)
    raw_banner: Optional[str] = None

    def encode(self) -> str:
        """Encodes the SSHMessage into a framed string for TCP transport."""
        if self.raw_banner:
            return f"{self.raw_banner}\r\n"
        return f"SSH_PACKET|{self.msg_type}|{json.dumps(self.payload)}"

    @staticmethod
    def decode(data_str: str) -> "SSHMessage":
        """
        Parses incoming TCP payload into an SSHMessage.
        Handles:
          - SSH-2.0 version banners
          - Framed SSH packets (SSH_PACKET|<type>|<json>)
          - Legacy plain-text payloads for backwards compatibility
        """
        clean = str(data_str).strip()
        
        # Check for SSH Version Banner
        if clean.startswith("SSH-2.0-"):
            return SSHMessage(msg_type=0, raw_banner=clean)
            
        # Check for framed SSH Packet
        if clean.startswith("SSH_PACKET|"):
            parts = clean.split("|", 2)
            if len(parts) == 3:
                try:
                    m_type = int(parts[1])
                    p_load = json.loads(parts[2])
                    return SSHMessage(msg_type=m_type, payload=p_load)
                except Exception:
                    pass
                    
        # Check for JSON representation
        if clean.startswith("{") and clean.endswith("}"):
            try:
                data = json.loads(clean)
                if "msg_type" in data:
                    m_type = data.pop("msg_type")
                    return SSHMessage(msg_type=m_type, payload=data)
            except Exception:
                pass
                
        # Legacy/Raw String fallback
        return SSHMessage(msg_type=-1, payload={"raw": clean})


# ==============================================================================
# SSH Channel Representation
# ==============================================================================

@dataclass
class SSHChannel:
    """Represents an active connection protocol channel."""
    channel_id: int
    recipient_channel: int = 0
    channel_type: str = "session"
    state: str = "open"
    window_size: int = 2097152
    max_packet_size: int = 32768
    command: Optional[str] = None
    pty: bool = False


# ==============================================================================
# SSH User Authentication Protocol (RFC 4252)
# ==============================================================================

class SSHUserAuthProtocol:
    """
    Manages SSH User Authentication Protocol.
    Handles service requests and credential verification.
    """

    DEFAULT_ACCOUNTS = {
        "admin": "password",
        "root": "toor",
        "user": "user123"
    }

    @staticmethod
    def create_service_request(service_name: str = "ssh-userauth") -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_SERVICE_REQUEST,
            payload={"service_name": service_name}
        )

    @staticmethod
    def create_service_accept(service_name: str = "ssh-userauth") -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_SERVICE_ACCEPT,
            payload={"service_name": service_name}
        )

    @staticmethod
    def create_userauth_request(
        username: str,
        password: str,
        service_name: str = "ssh-connection",
        method: str = "password"
    ) -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_USERAUTH_REQUEST,
            payload={
                "user": username,
                "service_name": service_name,
                "method": method,
                "password": password
            }
        )

    @staticmethod
    def create_userauth_success() -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_USERAUTH_SUCCESS,
            payload={"message": "Authentication successful"}
        )

    @staticmethod
    def create_userauth_failure(allowed_methods: list = None) -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_USERAUTH_FAILURE,
            payload={
                "authentications_that_can_continue": allowed_methods or ["password"],
                "partial_success": False
            }
        )

    @classmethod
    def verify(cls, username: str, password: str, config: Optional[dict] = None) -> bool:
        """Validates credentials against custom host config or default accounts."""
        if config and "users" in config and isinstance(config["users"], dict):
            user_table = config["users"]
            return user_table.get(username) == password
            
        return cls.DEFAULT_ACCOUNTS.get(username) == password


# ==============================================================================
# SSH Connection Protocol (RFC 4254)
# ==============================================================================

class SSHConnectionProtocol:
    """
    Manages SSH Connection Protocol:
    Multiplexes channels, handles session execution, data and close requests.
    """

    @staticmethod
    def create_channel_open(
        sender_channel: int = 0,
        channel_type: str = "session",
        window_size: int = 2097152,
        max_packet_size: int = 32768
    ) -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_CHANNEL_OPEN,
            payload={
                "channel_type": channel_type,
                "sender_channel": sender_channel,
                "initial_window_size": window_size,
                "maximum_packet_size": max_packet_size
            }
        )

    @staticmethod
    def create_channel_open_confirmation(
        recipient_channel: int,
        sender_channel: int,
        window_size: int = 2097152,
        max_packet_size: int = 32768
    ) -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_CHANNEL_OPEN_CONFIRMATION,
            payload={
                "recipient_channel": recipient_channel,
                "sender_channel": sender_channel,
                "initial_window_size": window_size,
                "maximum_packet_size": max_packet_size
            }
        )

    @staticmethod
    def create_channel_request(
        recipient_channel: int,
        request_type: str = "exec",
        command: str = "",
        want_reply: bool = True
    ) -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_CHANNEL_REQUEST,
            payload={
                "recipient_channel": recipient_channel,
                "request_type": request_type,
                "want_reply": want_reply,
                "command": command
            }
        )

    @staticmethod
    def create_channel_data(recipient_channel: int, data: str) -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_CHANNEL_DATA,
            payload={
                "recipient_channel": recipient_channel,
                "data": data
            }
        )

    @staticmethod
    def create_channel_eof(recipient_channel: int) -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_CHANNEL_EOF,
            payload={"recipient_channel": recipient_channel}
        )

    @staticmethod
    def create_channel_close(recipient_channel: int) -> SSHMessage:
        return SSHMessage(
            msg_type=SSH_MSG_CHANNEL_CLOSE,
            payload={"recipient_channel": recipient_channel}
        )
