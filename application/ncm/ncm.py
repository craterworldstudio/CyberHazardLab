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
    # HEALTH HELPERS
    # ========================================================

    def get_device_health(self, device):
        import time
        device = self.get_device(device)

        # Count interfaces
        total_interfaces = len(device.interfaces) if hasattr(device, 'interfaces') else 0
        up_interfaces = sum(1 for i in device.interfaces if getattr(i, 'link', None) is not None) if total_interfaces > 0 else 0

        # Count services
        services = getattr(device, 'services', [])
        total_services = len(services)
        running_services = sum(1 for s in services if getattr(s, 'status', '').lower() == 'running')

        # Status and Uptime
        status = getattr(device, "status", "OFF").upper()
        boot_time = getattr(device, "boot_time", None)
        
        if status == "ONLINE" and boot_time:
            uptime_sec = int(time.time() - boot_time)
            m, s = divmod(uptime_sec, 60)
            h, m = divmod(m, 60)
            uptime_str = f"{h:02d}:{m:02d}:{s:02d}"
        else:
            uptime_str = "00:00:00"

        return {
            "status": status,
            "uptime": uptime_str,
            "interfaces_active": up_interfaces,
            "interfaces_total": total_interfaces,
            "services_total": total_services,
            "services_running": running_services
        }

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

    # ========================================================
    # NETWORK / SUBNET MANAGEMENT
    # ========================================================

    def add_subnet(self, subnet, gateway=None):

        return self.simulation.add_subnet(
            subnet,
            gateway
        )

    def get_subnets(self):

        return self.simulation.network.subnets

    def get_subnet(self, ip):

        return self.simulation.network.get_subnet(ip)

    def get_gateway(self, ip):

        return self.simulation.network.get_gateway(ip)

    def remove_subnet(self, subnet):
        return self.simulation.remove_subnet(subnet)

    # ========================================================
    # SERVICE MANAGEMENT
    # ========================================================

    def add_service( self, device, name, protocol, port, status="stopped"
    ):

        device = self.get_device(device)

        if device not in self.simulation.hosts.values():
            raise ValueError(
                f"Services cannot be added to {device.name}"
            )

        return self.simulation.add_service( device, name, protocol, port, status
        )

    def start_service(self, device, service_name):

        device = self.get_device(device)

        return self.simulation.start_service(
            device,
            service_name
        )

    def stop_service(self, device, service_name):

        device = self.get_device(device)

        return self.simulation.stop_service(
            device,
            service_name
        )







    