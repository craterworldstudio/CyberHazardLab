from backend.core.node import Node
from backend.core.device import DeviceType
from backend.core.interface import NetworkInterface
from backend.core.mac import generate_mac

class Host(Node):
    def __init__(self, name: str, device_type: DeviceType = DeviceType.PC, network=None):
        super().__init__(name=name, device_type=device_type, network=network)
        self.forwarding_enabled = False
        
        # Default interface eth0
        self.add_interface(NetworkInterface(
            name="eth0",
            mac=generate_mac(),
            ip="0.0.0.0",
            subnet="0.0.0.0/0",
            owner=self
        ))
