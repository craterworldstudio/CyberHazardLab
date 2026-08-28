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
            network=self.network         
            )
        self.eth1 = NetworkInterface(
            name="eth1",
            mac=generate_mac(),
            ip="10.0.1.1",
            network=self.network             
            )

        self.add_interface(self.eth0)
        self.add_interface(self.eth1)  


    def add_interface(self, interface: NetworkInterface):
        self.interfaces.append(interface)

    def update_intf(self, interface: NetworkInterface, ip=None, subnet=None):
        interface.ip = ip if ip is not None else interface.ip
        interface.subnet = subnet if subnet is not None else interface.subnet
