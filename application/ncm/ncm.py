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

    def rename_device(self, old_name, new_name):
        return self.simulation.rename_device(old_name, new_name)

    # ========================================================
    # HEALTH HELPERS
    # ========================================================

    def get_device_health(self, device):
        import time
        device = self.get_device(device)

        # Count interfaces
        if hasattr(device, 'ports'):
            total_interfaces = len(device.ports)
            up_interfaces = sum(1 for p in device.ports.values() if getattr(p, 'link', None) is not None)
        else:
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

    def restart_device(self, device):
        import time
        device_obj = self.get_device(device)
        
        # Determine current running state of the whole sim
        sim_running = self.simulation.is_running
        
        if sim_running:
            device_obj.status = "ONLINE"
            device_obj.boot_time = time.time()
        else:
            device_obj.status = "OFFLINE"
            device_obj.boot_time = None
            
        return {"status": "success", "device": device}

    # ========================================================
    # INTERFACE HELPERS
    # ========================================================

    def get_interfaces(self, device):    #get all interfaces on the single device
        device = self.get_device(device)
        
        if hasattr(device, 'ports'):
            return list(device.ports.values())

        return list(getattr(device, 'interfaces', []))

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

    def get_subnet(self, ip: str) -> str:
        """Return the network address (CIDR) for a given IP based on known interface
        subnets. Defaults to /24 if no interface match found. Used by term_coms
        to auto-detect the egress interface for 'ip route add via' commands."""
        import ipaddress
        try:
            ip_obj = ipaddress.IPv4Address(str(ip).split('/')[0])
        except Exception:
            return None
        # Walk all devices to find a matching interface subnet
        for dev_dict in [self.simulation.hosts, self.simulation.routers, self.simulation.switches]:
            for dev in dev_dict.values():
                for intf in getattr(dev, 'interfaces', []):
                    subnet_str = getattr(intf, 'subnet', None)
                    if not subnet_str:
                        continue
                    try:
                        net = ipaddress.IPv4Network(subnet_str, strict=False)
                        if ip_obj in net:
                            return str(net)
                    except Exception:
                        continue
        # Fallback: synthesise a /24 network
        try:
            return str(ipaddress.IPv4Network(f"{ip}/24", strict=False))
        except Exception:
            return None


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
            
        if device in self.simulation.switches.values():
            if str(interface).startswith("Port-"):
                port_num = int(str(interface).split("-")[1])
                return device.remove_port(port_num)

        raise ValueError(
            f"Interfaces cannot be removed from {device.name}"
        )

    def update_interface(self, device, interface_name, ip=None, subnet=None, mac=None, netmask=None, gateway=None):
        import ipaddress
        device_obj = self.get_device(device)
        for intf in getattr(device_obj, 'interfaces', []):
            if intf.name == interface_name:
                if mac is not None:
                    intf.mac = mac

                # --- IP / Subnet resolution ---
                # Priority: explicit subnet > netmask > CIDR in IP field > existing subnet > /24 fallback

                # 1. If IP comes with CIDR notation, split it
                if ip and "/" in ip:
                    parts = ip.split("/")
                    ip = parts[0]
                    try:
                        net = ipaddress.ip_network(f"{ip}/{parts[1]}", strict=False)
                        subnet = str(net)
                    except ValueError:
                        subnet = f"{ip}/{parts[1]}"

                # 2. Convert dotted-decimal netmask to CIDR subnet string
                if netmask and ip and not subnet:
                    clean_ip = ip.split("/")[0] if ip else "0.0.0.0"
                    try:
                        net = ipaddress.ip_network(f"{clean_ip}/{netmask}", strict=False)
                        subnet = str(net)
                    except Exception:
                        pass

                # 3. If we still have no subnet but have an IP, also try converting existing stored netmask
                if not subnet and ip and ip != "0.0.0.0":
                    # Keep existing subnet if it's already set and matches same network
                    existing = getattr(intf, "subnet", None)
                    if existing and existing not in ("0.0.0.0/0", "0.0.0.0"):
                        try:
                            # Recalculate network with new IP but same prefix
                            pfx = ipaddress.ip_network(existing, strict=False).prefixlen
                            net = ipaddress.ip_network(f"{ip}/{pfx}", strict=False)
                            subnet = str(net)
                        except Exception:
                            pass

                # 4. Final fallback: /24 if still nothing
                if not subnet and ip and ip != "0.0.0.0":
                    try:
                        subnet = str(ipaddress.ip_network(f"{ip}/24", strict=False))
                    except Exception:
                        pass

                # Apply IP + subnet to the interface
                if hasattr(device_obj, 'update_intf'):
                    device_obj.update_intf(intf, ip=ip, subnet=subnet)
                else:
                    if ip is not None:
                        intf.ip = ip
                    if subnet is not None:
                        intf.subnet = subnet

                # --- Gateway handling ---
                # Accepting empty string means "clear the gateway"
                if gateway is not None:
                    gw_val = str(gateway).strip()
                    device_obj.default_gateway = gw_val if gw_val else None

                    # Rebuild default route for this device
                    # Remove any existing 0.0.0.0/0 route first
                    device_obj.routes = [
                        r for r in device_obj.routes
                        if str(r.get("destination", "")) != "0.0.0.0/0"
                    ]
                    if gw_val and hasattr(device_obj, 'add_route'):
                        out_intf = intf  # use the interface we just configured
                        device_obj.add_route("0.0.0.0/0", out_intf, next_hop=gw_val)

                return intf
        raise ValueError(f"Interface {interface_name} not found on {device_obj.name}")


    # ========================================================
    # NETWORK / SUBNET MANAGEMENT
    # ========================================================


    # ========================================================
    # SERVICE MANAGEMENT
    # ========================================================

    def add_service( self, device, name, protocol, port, status="stopped"
    ):

        device = self.get_device(device)

        return self.simulation.add_service( device, name, protocol, port, status
        )

    def get_services(self, device):
        device = self.get_device(device)
        return getattr(device, 'services', [])

    def remove_service(self, device, service_name):
        device = self.get_device(device)
        return self.simulation.remove_service(device, service_name)

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
