from dataclasses import dataclass, field
from typing import Any
import random

# DHCP Message Types (Option 53)
DHCPDISCOVER = "DHCPDISCOVER"
DHCPOFFER    = "DHCPOFFER"
DHCPREQUEST  = "DHCPREQUEST"
DHCPDECLINE  = "DHCPDECLINE"
DHCPACK      = "DHCPACK"
DHCPNAK      = "DHCPNAK"
DHCPRELEASE  = "DHCPRELEASE"

# Standard DHCP Option Codes
OPT_SUBNET_MASK    = 1
OPT_ROUTER         = 3
OPT_DNS_SERVER     = 6
OPT_REQUESTED_IP   = 50
OPT_LEASE_TIME     = 51
OPT_MESSAGE_TYPE   = 53
OPT_SERVER_ID      = 54
OPT_PARAM_REQUEST  = 55
OPT_RELAY_AGENT    = 82

@dataclass
class DHCPMessage:
    op: int = 1                     # 1 = BOOTREQUEST, 2 = BOOTREPLY
    htype: int = 1                  # 1 = Ethernet
    hlen: int = 6                   # Hardware address length
    hops: int = 0                   # Relay agent hop count
    xid: int = field(default_factory=lambda: random.randint(100000, 999999))
    secs: int = 0
    flags: int = 0
    ciaddr: str = "0.0.0.0"         # Client IP address
    yiaddr: str = "0.0.0.0"         # 'Your' (client) IP address
    siaddr: str = "0.0.0.0"         # Next server IP address
    giaddr: str = "0.0.0.0"         # Relay agent IP address
    chaddr: str = "00:00:00:00:00:00"  # Client hardware address (MAC)
    options: dict[int, Any] = field(default_factory=dict)

    @property
    def message_type(self) -> str | None:
        return self.options.get(OPT_MESSAGE_TYPE)

    @message_type.setter
    def message_type(self, val: str):
        self.options[OPT_MESSAGE_TYPE] = val

    def get_option(self, code: int, default: Any = None) -> Any:
        return self.options.get(code, default)

    def set_option(self, code: int, value: Any):
        self.options[code] = value
