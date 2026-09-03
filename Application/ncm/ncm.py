class NetworkConfigurationManager:

    def __init__(self, simulation):
        self.simulation = simulation

    # ========================================================
    # DEVICE HELPERS
    # ========================================================

    def get_devices(self):
        return {
            **self.simulation.hosts,
            **self.simulation.switches,
            **self.simulation.routers,
        }

    def get_device(self, name):
        devices = self.get_devices()
        
        if name not in devices:
            raise ValueError(f"Unknown device: {name}")

        return devices[name]

    # ========================================================
    # INTERFACE HELPERS
    # ========================================================

    def get_interfaces(self, device):    #get all interfaces on the single device
        device = self.get_device(device)

        return list(device.interfaces)

    def get_interface(self, device, interface):      # get the specific device
        device = self.get_device(device) if isinstance(device, str) else device

        if isinstance(interface, str):
            interface = device.get_interface(interface)

        if interface is None:
            raise ValueError(
                f"Interface does not exist on {device.name}"
            )

        if interface not in device.interfaces:
            raise ValueError(
                f"{interface.name} does not belong to {device.name}"
            )

        return interface


    # ========================================================
    # INTERFACE MANAGEMENT
    # ========================================================

    def add_interface(self, device, name=None, mac=None):
        device = self.get_device(device)

        if device in self.simulation.hosts.values():
            return self.simulation.add_host_interface(
                device,
                name=name,
                mac=mac
            )

        if device in self.simulation.routers.values():
            return self.simulation.add_router_interface(
                device,
                name=name,
                mac=mac
            )

        raise ValueError(
            f"Interfaces cannot be added to {device.name}"
        )

    def remove_interface(self, device, interface):
        device = self.get_device(device)

        if device in self.simulation.hosts.values():
            return self.simulation.remove_host_interface(
                device,
                interface
            )

        if device in self.simulation.routers.values():
            return self.simulation.remove_router_interface(
                device,
                interface
            )

        raise ValueError(
            f"Interfaces cannot be removed from {device.name}"
        )



    