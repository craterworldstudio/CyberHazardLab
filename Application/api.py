from backend.orchestrator import Simulation
from Application.ntm.ntm import NetworkTopologyManager
from backend.core.device import DeviceType


class NetworkAPI:

    def __init__(self):
        self.simulation = Simulation()
        self.ntm = NetworkTopologyManager(self.simulation)

    def get_network(self):
        devices = []

        for device in self.ntm.get_devices().values():
            device_type = getattr(device, "device_type", None)

            if isinstance(device_type, DeviceType):
                device_type = device_type.value
            elif device in self.simulation.switches.values():
                device_type = "switch"
            elif device in self.simulation.routers.values():
                device_type = "router"

            devices.append({
                "id": device.name,
                "name": device.name,
                "type": device_type
            })

        links = []

        for link in self.ntm.get_links():
            endpoint_a = link.endpointA
            endpoint_b = link.endpointB

            owner_a = getattr(endpoint_a, "owner", None)
            if owner_a is None:
                owner_a = getattr(endpoint_a, "switch", None)

            owner_b = getattr(endpoint_b, "owner", None)
            if owner_b is None:
                owner_b = getattr(endpoint_b, "switch", None)

            links.append({
                "source": getattr(owner_a, "name", None),
                "target": getattr(owner_b, "name", None)
            })

        return {
            "devices": devices,
            "links": links
        }

    def create_device(self, name, device_type):

        if not name:
            raise ValueError("Device name is required")

        if name in self.ntm.get_devices():
            raise ValueError(f"Device already exists: {name}")

        device_type = device_type.upper()

        if device_type == "HOST":
            device = self.simulation.add_host(
                name,
                device=DeviceType.PC
            )

        elif device_type == "SERVER":
            device = self.simulation.add_host(
                name,
                device=DeviceType.SERVER
            )

        elif device_type == "SWITCH":
            device = self.simulation.add_switch(name)

        elif device_type == "ROUTER":
            device = self.simulation.add_router(name)

        else:
            raise ValueError(
                f"Unsupported device type: {device_type}"
            )

        return {
            "id": device.name,
            "name": device.name,
            "type": device_type.lower()
        }