from dataclasses import dataclass, field
from typing import Any


@dataclass
class Packet:
    source_ip: str
    destination_ip: str
    protocol: str
    payload: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ARPPacket:

    operation: str

    sender_ip: str
    sender_mac: str

    target_ip: str
    target_mac: str | None = None


@dataclass
class TCPPacket:
    source_port: int
    destination_port: int
    sequence_number: int 
    acknowledgement_number: int 
    flags : set[str] = field(default_factory=set)
    payload: Any = None
