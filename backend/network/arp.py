from .packet import ARPPacket

from ..core.event import Event
from dataclasses import dataclass
from ..network.frame import EthernetFrame

class ARP:

    def __init__(self, network):
        self.network = network
        self.cache = {}


    def resolve(self, source, target_ip):

        if target_ip in self.cache.keys():
            return self.cache[target_ip]

        target = None

        #FROM INTERFACE NOT HOST
        req = ARPPacket(
            operation="REQUEST",
            sender_ip=source.ip,
            sender_mac=source.mac,
            target_ip=target_ip
        )

        frame = EthernetFrame(
            source_mac=source.mac,
            destination_mac="FF:FF:FF:FF:FF:FF",
            payload=req
        )

        self.network.add_event(Event(
            type="ARP_REQUEST",
            source=source.ip,
            destination=target_ip,
            protocol="ARP",
            metadata={
                "mac": source.mac
            }
        ))



        source.send(frame)

        return self.cache.get(target_ip)



    def receive(self, interface, packet):
        if packet.operation == "REQUEST":

            if packet.target_ip != interface.ip:
                return


            reply = ARPPacket(
                operation="REPLY",
                sender_ip=interface.ip,
                sender_mac=interface.mac,
                target_ip=packet.sender_ip,
                target_mac=packet.sender_mac
            )

            frame = EthernetFrame(
                source_mac= interface.mac,
                destination_mac=packet.sender_mac,
                payload=reply
            )

            interface.send(frame)

        if packet.operation == "REPLY":

            self.cache[packet.sender_ip] = packet.sender_mac

            self.network.add_event(Event(
                type="ARP_REPLY",
                source=packet.sender_ip,
                destination=packet.target_ip,
                protocol="ARP",
                metadata={
                    "mac": packet.sender_mac
                }

            ))