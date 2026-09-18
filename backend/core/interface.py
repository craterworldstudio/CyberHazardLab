from dataclasses import dataclass, field
from typing import Any
import ipaddress
from ..network.frame import EthernetFrame

@dataclass
class NetworkInterface:
    name: str
    mac: str
    ip: str | None = "0.0.0.0"
    subnet: str | None = "0.0.0.0/0"
    link: Any | None = None
    network: Any | None = None
    owner: Any | None = None
    status: str = "up"
    rx_buffer: list = field(default_factory=list)

    @property
    def arp(self):
        if self.owner and hasattr(self.owner, "arp"):
            return self.owner.arp
        return None

    def connect_link(self, link):
        if self.link is not None and self.link != link:
            raise ValueError(f"{self.name} is already connected to a link.")
        self.link = link

    def attach_network(self, network):
        self.network = network

    def send(self, frame: EthernetFrame):
        if getattr(self, "status", "up") != "up":
            return None
        if self.link is None:
            raise ValueError(f"{self.name} is not connected to a link")
        return self.link.transmit(frame, self)

    def receive(self, frame: EthernetFrame):
        if getattr(self, "status", "up") != "up":
            return None
        self.rx_buffer.append(frame)
        return None

    def process_rx_buffer(self):
        while self.rx_buffer:
            frame = self.rx_buffer.pop(0)
            if self.owner is not None:
                if hasattr(self.owner, "receive_frame"):
                    self.owner.receive_frame(self, frame)

    def send_ip_packet(self, packet):
        if self.owner is not None and hasattr(self.owner, "send_ip_packet"):
            return self.owner.send_ip_packet(packet, out_interface=self)
        raise ValueError(f"Interface {self.name} has no owner node to route packet")

    def __repr__(self):
        owner_name = getattr(self.owner, "name", "None")
        return f"Interface({owner_name}:{self.name}, ip={self.ip}, mac={self.mac})"
