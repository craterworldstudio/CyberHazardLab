from dataclasses import dataclass, field

from backend.network.packet import *
from backend.network.tcp import TCPConnection
from backend.network.udp import UDPConnection
from .service import Service
from .interface import NetworkInterface
from .mac import generate_mac
from .event import Event
from .device import DeviceType

@dataclass
class Host:
    name: str
    device_type: DeviceType = DeviceType.PC
    interfaces: list[NetworkInterface] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    network: Any = None

    def __post_init__(self):
        self.tcp_connections = {}
        self.udp_connections = {}
        self.last_icmp_result = None

        if not self.interfaces:
            self.add_interface(NetworkInterface(
                name="eth0", mac=generate_mac(), owner=self
            ))

    def add_service(self, service: Service):
        self.services.append(service)

    def add_interface(self, interface: NetworkInterface):
        interface.owner = self
        self.interfaces.append(interface)

    def get_interface(self, interface_name):

        for interface in self.interfaces:
            if interface.name == interface_name:
                return interface

        return None

    def get_ip(self):
        for interface in self.interfaces:
            if interface.ip is not None:
                return interface.ip

        return None

    def get_mac(self):
        for interface in self.interfaces:
            if interface.mac is not None:
                return interface.mac

    def receive_frame(self, interface, frame):

        payload = frame.payload
    
        if isinstance(payload, ARPPacket):
            return interface.arp.receive(
                interface,
                payload
            )
    
        if isinstance(payload, Packet):
            return self.receive_packet(
                interface,
                payload
            )
    
        return None

    def receive_packet(self, interface, packet):

        if packet.protocol.upper() == "TCP":
            return self.receive_tcp(interface, packet)

        if packet.protocol.upper() == "UDP":
            return self.receive_udp(interface, packet)

        if packet.protocol.upper() == "ICMP":
            return self.receive_icmp(interface, packet)


        return None



    def receive_tcp(self, interface, packet):
        print(
            f"{self.name} received TCP ", f"{packet.source_ip}:{packet.payload.source_port} -> ", f"{packet.destination_ip}:{packet.payload.destination_port}"
        )

        tcp_packet = packet.payload

        connection_key = (
            packet.source_ip,
            tcp_packet.source_port,
            packet.destination_ip,
            tcp_packet.destination_port
        )

        connection = self.tcp_connections.get( connection_key )

        if connection is None:
            service = None

            for candidate in self.services:

                if (
                    candidate.protocol.upper() == "TCP"
                    and candidate.port == tcp_packet.destination_port
                    and candidate.status.lower() == "running"
                ):
                    service = candidate
                    break

            if service is None:
                return None

            connection = TCPConnection(
                local_ip=packet.destination_ip,
                local_port=tcp_packet.destination_port,
                remote_ip=packet.source_ip,
                remote_port=tcp_packet.source_port,
                network=self.interfaces[0].network
            )

            connection.listen()

            self.tcp_connections[connection_key] = connection



        response = connection.receive(tcp_packet)
        if response is None:
            return None

        response_packet = Packet(
            source_ip=interface.ip,
            destination_ip=packet.source_ip,
            protocol="TCP",
            payload=response
        )

        return interface.send_ip_packet(response_packet)

    def add_tcp_connection(self, connection):
        key = (
            connection.local_ip,
            connection.local_port,
            connection.remote_ip,
            connection.remote_port
        )

        if key in self.tcp_connections:
            raise ValueError(
                f"TCP connection already exists: {key}"
            )

        self.tcp_connections[key] = connection
        return connection

    def get_tcp_connection( self, local_ip, local_port, remote_ip, remote_port ):
        key = (
            local_ip,
            local_port,
            remote_ip,
            remote_port
        )

        return self.tcp_connections.get(key)

    def remove_tcp_connection( self, local_ip, local_port, remote_ip, remote_port ):
        key = (
            local_ip,
            local_port,
            remote_ip,
            remote_port
        )

        return self.tcp_connections.pop(key, None)




    def receive_udp(self, interface, packet):

        udp = packet.payload
    
        if not isinstance(udp, UDPPacket):
            self.network.add_event(Event(
                type="UDP_DATAGRAM_DROPPED",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="UDP",
                metadata={
                    "reason": "INVALID_PACKET"
                }
            ))
            return None
    
        service = self.network.get_service_by_port(
            self,
            "UDP",
            udp.destination_port
        )
    
        if service is None:
            self.network.add_event(Event(
                type="UDP_PORT_UNREACHABLE",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="UDP",
                port=udp.destination_port,
                metadata={
                    "source_port": udp.source_port,
                    "destination_port": udp.destination_port,
                    "host": self.name,
                    "reason": "PORT_CLOSED"
                }
            ))
            return None
    
        if service.status.lower() != "running":
            self.network.add_event(Event(
                type="UDP_DATAGRAM_DROPPED",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="UDP",
                port=udp.destination_port,
                metadata={
                    "source_port": udp.source_port,
                    "destination_port": udp.destination_port,
                    "host": self.name,
                    "reason": "SERVICE_STOPPED"
                }
            ))
            return None
    
        # Find/create the UDP connection for this endpoint pair
        key = (
            packet.source_ip,
            udp.source_port,
            packet.destination_ip,
            udp.destination_port
        )
    
        connection = self.udp_connections.get(key)
    
        if connection is None:
            connection = UDPConnection(
                local_ip=packet.destination_ip,
                local_port=udp.destination_port,
                remote_ip=packet.source_ip,
                remote_port=udp.source_port,
                network=self.network
            )
    
            self.udp_connections[key] = connection
    
        return connection.receive(udp)

    def add_udp_connection(self, connection):
        key = (
            connection.local_ip,
            connection.local_port,
            connection.remote_ip,
            connection.remote_port
        )

        if key in self.udp_connections:
            raise ValueError(
                f"UDP connection already exists: {key}"
            )

        self.udp_connections[key] = connection
        return connection

    def get_udp_connection( self, local_ip, local_port, remote_ip, remote_port ):
        key = (
            local_ip,
            local_port,
            remote_ip,
            remote_port
        )

        return self.udp_connections.get(key)

    def remove_udp_connection( self, local_ip, local_port, remote_ip, remote_port ):
        key = (
            local_ip,
            local_port,
            remote_ip,
            remote_port
        )

        return self.udp_connections.pop(key, None)


    def receive_icmp(self, interface, packet):

        icmp = packet.payload

        if not isinstance(icmp, ICMPPacket):

            self.network.add_event(Event(
                type="ICMP_PACKET_DROPPED",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="ICMP",
                metadata={
                    "reason": "INVALID_PACKET"
                }
            ))

            return None

        if icmp.type == "ECHO_REQUEST":

            self.network.add_event(Event(
                type="ICMP_ECHO_REQUEST_RECEIVED",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="ICMP"
            ))

            reply = ICMPPacket(
                type="ECHO_REPLY",
                code=0,
                payload=icmp.payload
            )

            response = Packet(
                source_ip=interface.ip,
                destination_ip=packet.source_ip,
                protocol="ICMP",
                payload=reply
            )

            self.network.add_event(Event(
                type="ICMP_ECHO_REPLY_SENT",
                source=packet.destination_ip,
                destination=packet.source_ip,
                protocol="ICMP"
            ))

            return interface.send_ip_packet(response)

        if icmp.type == "ECHO_REPLY":

            self.network.add_event(Event(
                type="ICMP_ECHO_REPLY_RECEIVED",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="ICMP"
            ))

            self.last_icmp_result = {
                "type": "ECHO_REPLY",
                "source": packet.source_ip,
                "destination": packet.destination_ip,
                "payload": icmp.payload
            }

            return self.last_icmp_result

        if icmp.type == "TIME_EXCEEDED":

            self.network.add_event(Event(
                type="ICMP_TIME_EXCEEDED_RECEIVED",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="ICMP"
            ))

            self.last_icmp_result = {
                "type": "TIME_EXCEEDED",
                "source": packet.source_ip,
                "destination": packet.destination_ip,
                "payload": icmp.payload
            }

            return self.last_icmp_result

        if icmp.type == "DESTINATION_UNREACHABLE":

            self.network.add_event(Event(
                type="ICMP_DESTINATION_UNREACHABLE_RECEIVED",
                source=packet.source_ip,
                destination=packet.destination_ip,
                protocol="ICMP"
            ))

            self.last_icmp_result = {
                "type": "DESTINATION_UNREACHABLE",
                "source": packet.source_ip,
                "destination": packet.destination_ip,
                "payload": icmp.payload
            }
        
            return self.last_icmp_result

        return None