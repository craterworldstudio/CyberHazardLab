import ipaddress

from .packet import ARPPacket

from .frame import EthernetFrame
from ..core.event import Event
from ..core.interface import NetworkInterface
from ..core.mac import generate_mac
from .packet import *

class Router:

    def __init__(self, name, network):
        self.name = name
        self.network = network
        self.interfaces = []
        self.routes = []



        self.eth0 = NetworkInterface(
            name="eth0",
            mac=generate_mac(),
            ip="10.0.0.1",
            owner=self,
            subnet="10.0.0.0/24"
            )
        self.eth1 = NetworkInterface(
            name="eth1",
            mac=generate_mac(),
            ip="10.0.1.1",
            owner=self,
            subnet="10.0.1.0/24"
            )
        self.eth0.attach_network(self.network)
        self.eth1.attach_network(self.network)
        
        self.add_interface(self.eth0)
        self.add_interface(self.eth1)  


    def add_interface(self, interface: NetworkInterface):
        interface.owner = self
        self.interfaces.append(interface)

        if interface.subnet is not None:
            self.add_route(
                destination=interface.subnet,
                interface=interface
                )

    def update_intf(self, interface: NetworkInterface, ip=None, subnet=None):
        if ip is not None:
            interface.ip = ip
        if subnet is not None:
            if interface.subnet is not None:
                old_network = ipaddress.ip_network(interface.subnet)
                self.routes = [r for r in self.routes if not (r["interface"] == interface and r["destination"] == old_network)]

            interface.subnet = subnet

        if interface.subnet is not None:
            self.add_route(
                destination=subnet,
                interface=interface
                )
                
    

    def add_route(self, destination, interface, next_hop=None):
        route = {
            "destination": ipaddress.ip_network(destination),
            "interface": interface,
            "next_hop": next_hop
            }

        self.routes.append(route)

    def lookup_route(self, destination_ip):
        destination_ip = ipaddress.ip_address(destination_ip)

        matching_routes = [
            route
            for route in self.routes
            if destination_ip in route["destination"]
            ]

        if not matching_routes:
            return None

        return max(
            matching_routes,
            key=lambda route: route["destination"].prefixlen
        )

    def send_icmp_time_exceeded(self, packet, in_interface):

        #print(
        #f"TIME EXCEEDED: router={self.name}, "
        #f"interface={in_interface.name}, "
        #f"source={packet.source_ip}, "
        #f"destination={packet.destination_ip}, "
        #f"ttl={packet.ttl}"
        #)



        icmp = ICMPPacket(
            type="TIME_EXCEEDED",
            code=0,
            payload=packet
        )

        response = Packet(
            source_ip=in_interface.ip,
            destination_ip=packet.source_ip,
            protocol="ICMP",
            payload=icmp
        )

        self.network.add_event(Event(
            type="ICMP_TIME_EXCEEDED_SENT",
            source=in_interface.ip,
            destination=packet.source_ip,
            protocol="ICMP",
            metadata={
                "router": self.name,
                "interface": in_interface.name
            }
        ))


        return self.send_ip_packet(response)

    def send_icmp_destination_unreachable( self, packet, in_interface, code=0 ):  
        icmp = ICMPPacket(
            type="DESTINATION_UNREACHABLE",
            code=code,
            payload=packet
        )

        response = Packet(
            source_ip=in_interface.ip,
            destination_ip=packet.source_ip,
            protocol="ICMP",
            payload=icmp
        )

        self.network.add_event(Event(
            type="ICMP_DESTINATION_UNREACHABLE_SENT",
            source=in_interface.ip,
            destination=packet.source_ip,
            protocol="ICMP",
            metadata={
                "router": self.name,
                "interface": in_interface.name,
                "code": code
            }
        ))

        return self.send_ip_packet(response)

    def send_ip_packet(self, packet):

        #print(
        #f"ROUTER SEND: {self.name}: "
        #f"{packet.source_ip} -> {packet.destination_ip}"
        #)


        route = self.lookup_route(packet.destination_ip)

        if route is None:
            return "NO_ROUTE"

        out_interface = route["interface"]

        next_hop_ip = route["next_hop"]

        if next_hop_ip is None:
            next_hop_ip = packet.destination_ip

        destination_mac = out_interface.arp.resolve(
            out_interface,
            next_hop_ip
        )

        if destination_mac is None:
            return "ARP_FAILED"

        frame = EthernetFrame(
            source_mac=out_interface.mac,
            destination_mac=destination_mac,
            payload=packet
        )

        return out_interface.send(frame)

    def receive(self, frame, in_interface):
        
        #print(
        #    f"{self.name} received frame "
        #    f"on {in_interface.name}: {frame}"
        #)
    
        packet = frame.payload

        if isinstance(packet, ARPPacket):
            return in_interface.arp.receive(
                in_interface,
                packet
            )
        
        if not hasattr(packet, "destination_ip"):
            return "NOT_IP_PACKET"
        
    
        destination_ip = packet.destination_ip
        if destination_ip == in_interface.ip:
            return "ROUTER_DESTINATION"
        
        if packet.ttl <= 1:
            return self.send_icmp_time_exceeded(
                packet,
                in_interface
            )
        packet.ttl -= 1
        
        route = self.lookup_route(destination_ip)

        if route is None:
            return self.send_icmp_destination_unreachable( packet, in_interface )
    
        out_interface = route["interface"]
    
        if out_interface == in_interface:
            return "SAME_INTERFACE"   
    

        self.network.add_event(Event(
            type="PACKET_FORWARDED",
            source=packet.source_ip,
            destination=packet.destination_ip,
            protocol=packet.protocol,
            metadata={
                "router": self.name,
                "in_interface": in_interface.name,
                "out_interface": out_interface.name
                }
            ))
    
        return self.send_ip_packet(packet)

    def get_interface(self, interface_name):
        for interface in self.interfaces:
            if interface.name == interface_name:
                return interface
        return None






