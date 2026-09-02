class NetworkTopologyManager:

    def __init__(self, simulation):
        self.simulation = simulation

    def get_links(self):
        return self.simulation.get_links()

    def get_device_connections(self, name):
        device = self.get_device(name)
        connections = []

        for link in self.get_links():
            endpoint_a = link.endpointA
            endpoint_b = link.endpointB

            device_a = getattr(endpoint_a, "owner", None)

            if device_a is None:
                device_a = getattr(endpoint_a, "switch", None)

            device_b = getattr(endpoint_b, "owner", None)

            if device_b is None:
                device_b = getattr(endpoint_b, "switch", None)

            if device_a is device or device_b is device:
                connections.append(link)


            if link.endpointA is device or link.endpointB is device:
                connections.append(link)

        return connections

    def get_devices(self):
        return {
            **self.simulation.hosts,
            **self.simulation.switches,
            **self.simulation.routers,
        }

    def get_device(self, name):      # SINGLE DEVICEEE
        devices = self.get_devices()

        if name not in devices:
            raise ValueError(f"Unknown device: {name}")

        return devices[name]

    def connect(self, device_a, device_b):
        device_a = self.get_device(device_a)
        device_b = self.get_device(device_b)

        # Host/Router -> Switch
        if hasattr(device_a, "interfaces") and device_b in self.simulation.switches.values():
            if device_a in self.simulation.hosts.values():
                return self.simulation.connect_host_to_switch(
                    device_a,
                    device_b
                )

            interface = self._get_free_interface(device_a)

            return self.simulation.connect_switch_to_router(
                device_b,
                interface
            )

        # Switch -> Host/Router
        if device_a in self.simulation.switches.values() and hasattr(device_b, "interfaces"):
            if device_b in self.simulation.hosts.values():
                return self.simulation.connect_host_to_switch(
                    device_b,
                    device_a
                )

            interface = self._get_free_interface(device_b)

            return self.simulation.connect_switch_to_router(
                device_a,
                interface
            )

        # Router <-> Router
        if hasattr(device_a, "interfaces") and hasattr(device_b, "interfaces"):
            interface_a = self._get_free_interface(device_a)
            interface_b = self._get_free_interface(device_b)

            return self.simulation.connect_interfaces(
                interface_a,
                interface_b
            )

        if device_a in self.simulation.switches.values() and device_b in self.simulation.switches.values():
            return self.simulation.connect_switches(device_a, device_b)

        raise ValueError(
            f"Cannot connect {device_a.name} to {device_b.name}"
        )

    def _get_free_interface(self, device):
        for interface in device.interfaces:
            if interface.link is None:
                return interface

        if device in self.simulation.hosts.values():
            return self.simulation.add_host_interface(device)

        if device in self.simulation.routers.values():
            return self.simulation.add_router_interface(device)

        raise ValueError(
            f"Device {device.name} has no free interfaces"
        )



