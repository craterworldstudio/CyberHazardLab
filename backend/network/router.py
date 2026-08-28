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
            network=self.network,
            owner=self         
            )
        self.eth1 = NetworkInterface(
            name="eth1",
            mac=generate_mac(),
            ip="10.0.1.1",
            network=self.network,
            owner=self           
            )

        self.add_interface(self.eth0)
        self.add_interface(self.eth1)  


    def add_interface(self, interface: NetworkInterface):
        self.interfaces.append(interface)

    def update_intf(self, interface: NetworkInterface, ip=None, subnet=None):
        interface.ip = ip if ip is not None else interface.ip
        interface.subnet = subnet if subnet is not None else interface.subnet

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
            return self.network.arp.receive(
                in_interface,
                packet
            )
        
        if not hasattr(packet, "destination_ip"):
            return "NOT_IP_PACKET"
        
    
        destination_ip = packet.destination_ip
    
        if destination_ip == in_interface.ip:
            return "ROUTER_DESTINATION"
    
        out_interface = self.get_interface_for_ip(destination_ip)
    
        if out_interface is None:
            return "NO_ROUTE"
    
        destination_mac = self.network.arp.resolve(
            out_interface,
            destination_ip
        )
    
        if destination_mac is None:
            return "ARP_FAILED"
    
        new_frame = EthernetFrame(
            source_mac=out_interface.mac,
            destination_mac=destination_mac,
            payload=packet
        )
    
        return out_interface.send(new_frame)