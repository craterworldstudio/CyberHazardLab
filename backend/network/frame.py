from dataclasses import dataclass
from .packet import Packet

@dataclass
class EthernetFrame:
    source_mac: str
    destination_mac: str
    payload: Packet


    