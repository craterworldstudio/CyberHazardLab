from backend.core.node import Node
from backend.core.device import DeviceType

class Router(Node):
    def __init__(self, name: str, network=None):
        super().__init__(name=name, device_type=DeviceType.OTHER, network=network)
        self.forwarding_enabled = True
        self.auto_routes = "inherit"
        self.default_gateway = None

    @property
    def ip_forwarding(self):
        return self.forwarding_enabled

    @ip_forwarding.setter
    def ip_forwarding(self, val):
        self.forwarding_enabled = bool(val)

    def __getattr__(self, item: str):
        if item.startswith("eth"):
            intf = self.get_interface(item)
            if intf:
                return intf
            from backend.core.interface import NetworkInterface
            from backend.core.mac import generate_mac
            new_intf = NetworkInterface(
                name=item,
                mac=generate_mac(),
                owner=self,
                ip="0.0.0.0",
                subnet="0.0.0.0/0"
            )
            self.add_interface(new_intf)
            return new_intf
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{item}'")
