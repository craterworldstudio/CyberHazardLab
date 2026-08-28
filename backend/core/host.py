from dataclasses import dataclass, field
from .service import Service
from .interface import NetworkInterface
from .mac import generate_mac

@dataclass
class Host:
    name: str
    interfaces: list[NetworkInterface] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)

    def __post_init__(self):
        if not self.interfaces:
            self.add_interface(NetworkInterface(
                name="eth0", mac=generate_mac()
            ))

    def add_service(self, service: Service):
        self.services.append(service)

    def add_interface(self, interface: NetworkInterface):
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

