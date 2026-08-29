import ipaddress

from .arp import ARPPacket

from .frame import EthernetFrame

from ..core.interface import NetworkInterface
from ..core.mac import generate_mac

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

    def get_interface_for_ip(self, ip):
        address = ipaddress.ip_address(ip)

        for interface in self.interfaces:
            if interface.subnet is None:
                continue

            subnet = ipaddress.ip_network(interface.subnet)
            if address in subnet:
                return interface

        return None

    def receive(self, frame, in_interface):
        
        print(
            f"{self.name} received frame "
            f"on {in_interface.name}: {frame}"
        )
    
        packet = frame.payload

        if isinstance(packet, ARPPacket):
            return self.in_interface.arp.receive(
                in_interface,
                packet
            )
        
        if not hasattr(packet, "destination_ip"):
            return "NOT_IP_PACKET"
        
    
        destination_ip = packet.destination_ip
    
        if destination_ip == in_interface.ip:
            return "ROUTER_DESTINATION"

        route = self.lookup_route(destination_ip)

        if route is None:
            return "NO_ROUTE"
    
        out_interface = route["interface"]
    
        if out_interface == in_interface:
            return "SAME_INTERFACE"

        next_hop_ip = route["next_hop"]

        if next_hop_ip is None:
            next_hop_ip = destination_ip
    
        destination_mac = self.out_interface.arp.resolve(
            out_interface,
            next_hop_ip
        )
    
        if destination_mac is None:
            return "ARP_FAILED"
    
        new_frame = EthernetFrame(
            source_mac=out_interface.mac,
            destination_mac=destination_mac,
            payload=packet
        )

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
    
        return out_interface.send(new_frame)
