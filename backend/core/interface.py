from dataclasses import dataclass
from ..network.link import Link
from ..network.arp import ARP
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
    owner: Any | None = None
    arp: ARP | None = None

    def connect_link(self, link):
        self.link = link

    def attach_network(self, network):
        self.network = network
        self.arp = ARP(self.network)

    def send(self, frame):
        if self.link is None:
            raise ValueError(
                f"{self.name} is not connected to a link"
            )
        
        return self.link.transmit(frame, self)

    def receive(self, frame):
        if self.owner is not None:
            return self.owner.receive(frame, self)

        print(f"\n{self.name} received frame: {frame}")

        payload = frame.payload

        if isinstance(payload, ARPPacket):

            self.arp.receive(
                self, payload
            )

            return

    def send_ip_packet(self, packet):

        if self.network is None:
            raise ValueError(
                f"{self.name} is not attached to a network"
            )

        source_subnet = self.network.get_subnet(self.ip)
        destination_subnet = self.network.get_subnet(
            packet.destination_ip
        )

        if source_subnet is None:
            raise ValueError(
                f"{self.ip} does not belong to a known subnet"
            )

        if destination_subnet is None:
            raise ValueError(
                f"{packet.destination_ip} does not belong to a known subnet"
            )

        if source_subnet == destination_subnet:
            next_hop_ip = packet.destination_ip
        else:
            next_hop_ip = self.network.get_gateway(self.ip)



        destination_mac = self.arp.resolve(
            self,
            next_hop_ip
        )

        if destination_mac is None:
            return "ARP_FAILED"

        frame = EthernetFrame(
            source_mac=self.mac,
            destination_mac=destination_mac,
            payload=packet
        )

        return self.send(frame)

