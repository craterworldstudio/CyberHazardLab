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
    pcap_buffer: list = field(default_factory=list)

    @property
    def arp(self):
        if self.owner and hasattr(self.owner, "arp"):
            return self.owner.arp
        return None

    def _record_pcap(self, frame):
        import time
        if not hasattr(self, "pcap_buffer") or self.pcap_buffer is None:
            self.pcap_buffer = []
        if len(self.pcap_buffer) >= 2000:
            self.pcap_buffer.pop(0)
        self.pcap_buffer.append((time.time(), frame))

    def get_pcap_bytes(self) -> bytes:
        from ..network.pcap import PCAPWriter
        buffer = getattr(self, "pcap_buffer", []) or []
        return PCAPWriter.build_pcap(buffer)

    def clear_pcap(self):
        self.pcap_buffer = []

    def connect_link(self, link):
        if self.link is not None and self.link != link:
            raise ValueError(f"{self.name} is already connected to a link.")
        self.link = link

    def attach_network(self, network):
        self.network = network

    def send(self, frame: EthernetFrame):
        if getattr(self, "status", "up") != "up":
            return None
        self._record_pcap(frame)
        if self.link is None:
            raise ValueError(f"{self.name} is not connected to a link")
        return self.link.transmit(frame, self)

    def receive(self, frame: EthernetFrame):
        if getattr(self, "status", "up") != "up":
            return None
        self._record_pcap(frame)
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
