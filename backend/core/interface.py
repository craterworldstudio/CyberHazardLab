from dataclasses import dataclass
from ..network.link import Link
from typing import Any
from ..network.frame import EthernetFrame
from ..network.arp import ARPPacket
from .event import Event

@dataclass
class NetworkInterface:
    name: str
    mac: str
    ip: str | None = None
    link: Link = None
    network: Any |None = None
    subnet: str | None = None

    def connect_link(self, link):
        self.link = link

    def attach_network(self, network):
        self.network = network

    def send(self, frame):
        if self.link is None:
            raise ValueError(
                f"{self.name} is not connected to a link"
            )
        
        return self.link.transmit(frame, self)

    def receive(self, frame):
        print(f"\n{self.name} received frame: {frame}")

        payload = frame.payload

        if isinstance(payload, ARPPacket):

            self.network.arp.receive(
                self, payload
            )

            return

    def send_ip_packet(self, packet):

        if self.network is None:
            raise ValueError(
                f"{self.name} is not attached to a network"
            )

        destination_mac = self.network.arp.resolve(
            self,
            packet.destination_ip
        )

        if destination_mac is None:
            return "ARP_FAILED"

        frame = EthernetFrame(
            source_mac=self.mac,
            destination_mac=destination_mac,
            payload=packet
        )

        return self.send(frame)

