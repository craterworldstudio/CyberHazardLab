from application.term_coms import TerminalCommandHandler
from backend.core.event import Event
from backend.orchestrator import Simulation

class API:

    def __init__(self, ntm, ncm, state_manager):
        self.ntm = ntm
        self.ncm = ncm
        self.state_manager = state_manager

    # ========================================================
    # REQUEST DISPATCH
    # ========================================================

    def handle(self, method, path, body=None):
        try:
            return self._handle_internal(method, path, body)
        except ValueError as e:
            try:
                
                # Try to extract device name from path (e.g. /api/ncm/devices/HOST-05/services) or body
                source_dev = "API"
                dev_meta = {}
                parts = [p for p in path.split("/") if p]
                if len(parts) >= 4 and parts[0] == "api" and parts[2] == "devices":
                    source_dev = parts[3]
                elif body and isinstance(body, dict) and "device" in body:
                    source_dev = body["device"]
                    
                if source_dev != "API":
                    dev_meta = {"host": source_dev} # use host/router/switch interchangeably for UI catching it
                
                event = Event(
                    type="SYSTEM_ERROR",
                    source=source_dev,
                    destination="SYSTEM",
                    severity="HIGH",
                    metadata={"error": str(e), "path": path, "method": method, **dev_meta}
                )
                self.ntm.simulation.network.add_event(event)
                
                # Double check that it actually got added to the list
                count = len(self.ntm.simulation.network.events)
                with open("api_debug.log", "a") as f:
                    f.write(f"SUCCESS: Added event {e}. Total events now: {count}\n")
            except Exception as inner_e:
                with open("api_debug.log", "a") as f:
                    f.write(f"FAILED to add event: {inner_e}\n")
            raise e

    def _handle_internal(self, method, path, body=None):
        method = method.upper()
        path = path.split("?", 1)[0]

        parts = [
            part
            for part in path.split("/")
            if part
        ]

        if not parts or parts[0] != "api":
            raise ValueError(
                "Unknown API path"
            )

        if len(parts) < 2:
            raise ValueError(
                "API manager was not specified"
            )

        manager = parts[1].lower()
        resource = parts[2:]

        body = body or {}

        if manager == "ntm":
            return self._handle_ntm(
                method,
                resource,
                body
            )

        if manager == "ncm":
            return self._handle_ncm(
                method,
                resource,
                body
            )

        if manager == "simulation":
            return self._handle_simulation(method, resource, body)

        raise ValueError(
            f"Unknown API manager: {manager}"
        )

    # ========================================================
    # SIMULATION
    # ========================================================

    def _handle_simulation(self, method, resource, body):
        if method == "GET" and resource == ["settings"]:
            return getattr(self.ntm.simulation, "settings", {
                "network_name": getattr(self.ntm.simulation, "name", "Cyber Hazard Network"),
                "dhcp_mode": "manual",
                "dns_mode": "manual",
                "default_ttl": 64
            })
            
        if method == "POST" and resource == ["settings"]:
            if not hasattr(self.ntm.simulation, "settings"):
                self.ntm.simulation.settings = {}
            self.ntm.simulation.settings.update(body)
            if "network_name" in body:
                self.ntm.simulation.name = body["network_name"]
            self.state_manager.save()
            return {"status": "success", "settings": self.ntm.simulation.settings}

        if method == "POST" and resource == ["reset"]:
            
            self.ntm.simulation = Simulation()
            self.ncm.simulation = self.ntm.simulation
            self.state_manager.simulation = self.ntm.simulation
            self.state_manager.reset()
            return {"status": "success"}

        if method == "GET" and resource == ["export"]:
            self.state_manager.save()
            return self.state_manager.load()

        if method == "POST" and resource == ["import"]:
            self.ntm.simulation = Simulation()
            self.ncm.simulation = self.ntm.simulation
            self.state_manager.simulation = self.ntm.simulation
            
            sim_data = body.get("simulation", {})
            layout_data = body.get("layout", {})
            
            self.ntm.simulation.name = sim_data.get("name", "Cyber Hazard Network")
            self.ntm.simulation.settings = sim_data.get("settings", {})
            
            # Devices
            for d in sim_data.get("devices", []):
                self.ntm.create_device(name=d["name"], device_type=d["type"])
                
            # Links
            for l in sim_data.get("links", []):
                try:
                    self.ntm.connect(l["endpoint_a"], l["endpoint_b"])
                except Exception:
                    pass
                    
            # Interfaces
            for device_name, intfs in sim_data.get("interfaces", {}).items():
                for intf in intfs:
                    try:
                        self.ncm.update_interface(device_name, intf["name"], ip=intf.get("ip"), subnet=intf.get("subnet"), mac=intf.get("mac"))
                    except Exception:
                        pass
                        
            # Subnets
            for subnet, data in sim_data.get("subnets", {}).items():
                try:
                    self.ncm.add_subnet(subnet, data.get("gateway"))
                except Exception:
                    pass
                    
            # Services
            for device_name, svcs in sim_data.get("services", {}).items():
                for s in svcs:
                    try:
                        svc_obj = self.ncm.add_service(device_name, s["name"], s["protocol"], s["port"], s.get("status", "stopped"))
                        if "config" in s:
                            svc_obj.config = s["config"]
                    except Exception:
                        pass
                        
            # Routes
            import ipaddress
            for router_name, routes in sim_data.get("routes", {}).items():
                if not routes:
                    continue
                router = self.ntm.get_device(router_name)
                if router:
                    router.routes = []
                    for r in routes:
                        try:
                            # Re-map interface string to actual object
                            intf_name = r.get("interface")
                            intf_obj = None
                            if intf_name:
                                for i in router.interfaces:
                                    if i.name == intf_name:
                                        intf_obj = i
                                        break
                            dest_val = r["destination"]
                            if isinstance(dest_val, dict):
                                dest_str = f"{dest_val.get('network_address', '0.0.0.0')}/{ipaddress.IPv4Address(dest_val.get('netmask', '255.255.255.0'))}"
                                # Quick hack: just use network_address/netmask, though calculating prefixlen from netmask is hard without ipaddress.IPv4Network. 
                                # Better: 
                                dest_str = f"{dest_val.get('network_address', '0.0.0.0')}/{dest_val.get('netmask', '255.255.255.0')}"
                            else:
                                dest_str = str(dest_val)
                                
                            router.add_route(dest_str, intf_obj, r.get("next_hop"))
                        except Exception:
                            pass
                            
            # MAC Tables
            for switch_name, macs in sim_data.get("mac_tables", {}).items():
                switch = self.ntm.get_device(switch_name)
                if switch:
                    switch.mac_table = dict(macs)
                    
            # ARP Caches (validate against current device MACs to prevent stale poisoning)
            for device_name, intf_arps in sim_data.get("arp_caches", {}).items():
                device = self.ntm.get_device(device_name)
                if device:
                    for intf_name, cache in intf_arps.items():
                        for i in getattr(device, "interfaces", []):
                            if i.name == intf_name and hasattr(i, "arp") and i.arp:
                                for ip_k, mac_v in cache.items():
                                    target_dev = next((d for d in self.ntm.get_devices().values() if hasattr(d, "interfaces") and any(di.ip == ip_k for di in d.interfaces)), None)
                                    if target_dev:
                                        target_intf = next((di for di in target_dev.interfaces if di.ip == ip_k), None)
                                        if target_intf and target_intf.mac == mac_v:
                                            i.arp.cache[ip_k] = mac_v
                                    else:
                                        i.arp.cache[ip_k] = mac_v
                                break
                        
            self.state_manager.save(layout=layout_data)
            return {"status": "success"}

        if method == "POST" and resource == ["run"]:
            self.ntm.simulation.run()
            self.state_manager.save()
            return {"status": "running"}

        if method == "POST" and resource == ["stop"]:
            self.ntm.simulation.stop()
            self.state_manager.save()
            return {"status": "stopped"}

        if method == "POST" and resource == ["validate"]:
            updated = self.ntm.simulation.validate()
            self.state_manager.save()
            return {"status": "validated", "updated": updated}

        if method == "POST" and resource == ["forge"]:
            proto = body.get("protocol", "TCP").upper()
            src_port = body.get("source_port")
            dst_port = body.get("destination_port")
            src_ip = body.get("source_ip")
            dst_ip = body.get("destination_ip")
            payload = body.get("payload", "")
            
            source_device = None
            all_l3 = list(self.ntm.simulation.hosts.values()) + list(self.ntm.simulation.routers.values())
            
            if src_ip:
                for dev in all_l3:
                    for intf in dev.interfaces:
                        if intf.ip == src_ip:
                            source_device = dev
                            source_intf = intf
                            break
                    if source_device: break
                    
            if not source_device:
                for dev in all_l3:
                    for intf in dev.interfaces:
                        if intf.link is not None:
                            source_device = dev
                            source_intf = intf
                            break
                    if source_device: break
            
            if not source_device or not source_intf:
                raise ValueError("No valid entry point (connected node) found in the network to inject the payload.")
                
            if not src_ip or src_ip == "0.0.0.0":
                src_ip = source_intf.ip if (source_intf.ip and source_intf.ip != "0.0.0.0") else "10.0.0.100"
                
            from backend.network.packet import Packet, TCPPacket, UDPPacket, ICMPPacket
            
            inner_payload = None
            if proto == "TCP":
                inner_payload = TCPPacket(
                    source_port=int(src_port) if src_port else 49152,
                    destination_port=int(dst_port) if dst_port else 80,
                    sequence_number=1,
                    acknowledgement_number=0,
                    payload=payload
                )
            elif proto == "UDP":
                inner_payload = UDPPacket(
                    source_port=int(src_port) if src_port else 49152,
                    destination_port=int(dst_port) if dst_port else 53,
                    payload=payload
                )
            else:
                inner_payload = ICMPPacket(type="ECHO_REQUEST", payload=payload)
                
            packet = Packet(
                source_ip=src_ip,
                destination_ip=dst_ip,
                protocol=proto,
                payload=inner_payload,
                ttl=64
            )
            
            from backend.core.event import Event
            self.ntm.simulation.network.add_event(Event(
                type="PAYLOAD_FORGED",
                source=src_ip,
                destination=dst_ip,
                protocol=proto,
                severity="WARNING",
                metadata={"dst_port": dst_port, "src_port": src_port, "payload_size": len(payload), "injection_point": source_device.name}
            ))
            
            source_device.send_ip_packet(packet, out_interface=source_intf)
            return {"status": "injected"}

        if method == "GET" and resource == ["poll"]:
            events = self.ntm.simulation.network.events
            devices = [self._serialize_device(d) for d in self.all_devices()]
            return {
                "status": "running" if self.ntm.simulation.is_running else "stopped",
                "devices": devices,
                "events": [
                    {
                        "type": e.type,
                        "source": e.source,
                        "destination": e.destination,
                        "protocol": e.protocol,
                        "port": e.port,
                        "severity": getattr(e, "severity", "INFO"),
                        "timestamp": e.timestamp.isoformat(),
                        "metadata": e.metadata
                    }
                    for e in events[-50:] # last 50 events to avoid massive payloads
                ]
            }

        if method == "GET" and resource == ["events"]:
            events = self.ntm.simulation.network.events
            return [
                {
                    "type": e.type,
                    "source": e.source,
                    "destination": e.destination,
                    "protocol": e.protocol,
                    "port": e.port,
                    "severity": getattr(e, "severity", "INFO"),
                    "timestamp": e.timestamp.isoformat(),
                    "metadata": e.metadata
                }
                for e in events
            ]
            
        raise ValueError("Unknown SIMULATION endpoint")
        
    def all_devices(self):
        return [
            *self.ntm.simulation.hosts.values(),
            *self.ntm.simulation.switches.values(),
            *self.ntm.simulation.routers.values()
        ]

    # ========================================================
    # NTM
    # ========================================================

    def _handle_ntm(self, method, resource, body):

        # GET /api/ntm/devices
        if (
            method == "GET"
            and resource == ["devices"]
        ):
            return [
                self._serialize_device(device)
                for device in self.ntm.get_devices().values()
            ]

        # GET /api/ntm/devices/HOST-01
        if ( method == "GET" and len(resource) == 2 and resource[0] == "devices"):
            device = self.ntm.get_device( resource[1] )
            if not device:
                return {"error": "Device not found"}, 404

            return self._serialize_device(device)

        # GET /api/ntm/links
        if (
            method == "GET"
            and resource == ["links"]
        ):
            return [ self._serialize_link(link) for link in self.ntm.get_links() ]

        # GET /api/ntm/devices/HOST-01/connections
        if ( method == "GET" and len(resource) == 3 and resource[0] == "devices" and resource[2] == "connections"):
            links = self.ntm.get_device_connections( resource[1] )

            return [
                self._serialize_link(link)
                for link in links
            ]

        # POST /api/ntm/devices
        if ( method == "POST" and resource == ["devices"] ):
            device = self.ntm.create_device(
                name=body["name"],
                device_type=body.get( "type", "pc" ),
                subnet=body.get("subnet")
            )
            self.state_manager.save()

            return self._serialize_device(
                device
            )

        # DELETE /api/ntm/devices
        if (method == "DELETE" and resource[0] == "devices"):
            device = self.ntm.remove_device(body["name"])
            self.state_manager.save()
            return self._serialize_device(device)

        # POST /api/ntm/connect
        if ( method == "POST" and resource == ["connect"] ):
            link = self.ntm.connect(
                body["device_a"],
                body["device_b"]
            )
            self.state_manager.save()

            return self._serialize_link(
                link
            )

        # POST /api/ntm/disconnect
        if (
            method == "POST"
            and resource == ["disconnect"]
        ):
            link = self.ntm.disconnect(
                body["device_a"],
                body["device_b"]
            )
            self.state_manager.save()

            return self._serialize_link(
                link
            )

        # GET /api/ntm/layout
        if method == "GET" and resource == ["layout"]:
            state = self.state_manager.load()
            return state.get("layout", {}) if state else {}

        # POST /api/ntm/layout
        if method == "POST" and resource == ["layout"]:
            self.state_manager.save(layout=body)
            return {"status": "success"}

        raise ValueError(
            "Unknown NTM endpoint"
        )

    # ========================================================
    # NCM
    # ========================================================

    def _handle_ncm(self, method, resource, body):

        # GET /api/ncm/devices
        if (
            method == "GET"
            and resource == ["devices"]
        ):
            return [
                self._serialize_device(device)
                for device in self.ncm.get_devices().values()
            ]

        # GET /api/ncm/devices/HOST-01/interfaces
        if (
            method == "GET"
            and len(resource) == 3
            and resource[0] == "devices"
            and resource[2] == "interfaces"
        ):
            interfaces = self.ncm.get_interfaces(
                resource[1]
            )

            return [
                self._serialize_interface(interface)
                for interface in interfaces
            ]

        # GET /api/ncm/devices/HOST-01/health
        if (
            method == "GET"
            and len(resource) == 3
            and resource[0] == "devices"
            and resource[2] == "health"
        ):
            health = self.ncm.get_device_health(
                resource[1]
            )

            return self._serialize(health)

        # SERVICES API
        # GET /api/ncm/devices/<device>/services
        if method == "GET" and len(resource) == 3 and resource[0] == "devices" and resource[2] == "services":
            services = self.ncm.get_services(resource[1])
            return [self._serialize(s) for s in services]

        # POST /api/ncm/devices/<device>/services
        if method == "POST" and len(resource) == 3 and resource[0] == "devices" and resource[2] == "services":
            config = body.get("config", {})
            service = self.ncm.add_service(
                resource[1],
                body["name"],
                body["protocol"],
                int(body["port"])
            )
            if config:
                service.config = config
            self.state_manager.save()
            return self._serialize(service)

        # DELETE /api/ncm/devices/<device>/services/<service>
        if method == "DELETE" and len(resource) == 4 and resource[0] == "devices" and resource[2] == "services":
            self.ncm.remove_service(resource[1], resource[3])
            self.state_manager.save()
            return {"status": "success"}

        # POST /api/ncm/devices/<device>/services/<service>/start
        if method == "POST" and len(resource) == 5 and resource[0] == "devices" and resource[2] == "services" and resource[4] == "start":
            self.ncm.start_service(resource[1], resource[3])
            self.state_manager.save()
            return {"status": "started"}

        # POST /api/ncm/devices/<device>/services/<service>/stop
        if method == "POST" and len(resource) == 5 and resource[0] == "devices" and resource[2] == "services" and resource[4] == "stop":
            self.ncm.stop_service(resource[1], resource[3])
            self.state_manager.save()
            return {"status": "stopped"}

        # POST /api/ncm/interfaces
        if (
            method == "POST"
            and resource == ["interfaces"]
        ):
            interface = self.ncm.add_interface(
                body["device"],
                name=body.get("name"),
                mac=body.get("mac")
            )

            self.state_manager.save()

            return self._serialize_interface(
                interface
            )

        # PUT /api/ncm/devices/<device>/interfaces/<interface>
        if method == "PUT" and len(resource) == 4 and resource[0] == "devices" and resource[2] == "interfaces":
            interface = self.ncm.update_interface(
                resource[1],
                resource[3],
                ip=body.get("ip"),
                subnet=body.get("subnet")
            )
            self.state_manager.save()
            return self._serialize_interface(interface)

        # DELETE /api/ncm/interfaces
        if (
            method == "DELETE"
            and resource == ["interfaces"]
        ):
            interface = self.ncm.remove_interface(
                body["device"],
                body["interface"]
            )

            self.state_manager.save()

            return self._serialize_interface(
                interface
            )

        # POST /api/ncm/devices/<device>/config
        if method == "POST" and len(resource) == 3 and resource[0] == "devices" and resource[2] == "config":
            sim = self.ntm.simulation
            device = sim.hosts.get(resource[1]) or sim.routers.get(resource[1]) or sim.switches.get(resource[1])
            if not device:
                return {"error": "Device not found"}, 404
                
            if "auto_routes" in body:
                device.auto_routes = bool(body["auto_routes"])
            if "auto_mac_learning" in body:
                device.auto_mac_learning = bool(body["auto_mac_learning"])
                
            self.state_manager.save()
            return {"success": True}

        # POST /api/ncm/devices/<device>/terminal
        if method == "POST" and len(resource) == 3 and resource[0] == "devices" and resource[2] == "terminal":
            command = body.get("command", "")
            
            # Simple terminal logic placeholder
            output = f"Nox OS > Command '{command}' not recognized."
            sim = self.ntm.simulation
            device = sim.hosts.get(resource[1]) or sim.routers.get(resource[1]) or sim.switches.get(resource[1])
            if not device:
                return {"output": "Device not found."}

            
            handler = TerminalCommandHandler(sim, self.ncm, self.state_manager)
            output = handler.execute(device, command)
            
            return {"output": output}

        # POST /api/ncm/devices/<device>/restart
        if method == "POST" and len(resource) == 3 and resource[0] == "devices" and resource[2] == "restart":
            result = self.ncm.restart_device(resource[1])
            self.state_manager.save()
            return self._serialize(result)


        




        # GET /api/ncm/gateway/<ip>
        if ( method == "GET" and len(resource) == 2 and resource[0] == "gateway"):
            return self._serialize( self.ncm.get_gateway( resource[1] )
            )

        raise ValueError(
            "Unknown NCM endpoint"
        )












    # ========================================================
    # SERIALIZATION
    # ========================================================

    def _serialize_device(self, device):

        if device in self.ntm.simulation.hosts.values():

            device_type = getattr(
                getattr( device, "device_type", None ), "value", "host")

        elif device in self.ntm.simulation.switches.values():
            device_type = "switch"

        elif device in self.ntm.simulation.routers.values():
            device_type = "router"

        else:
            device_type = "unknown"

        result = {
            "name": device.name,
            "type": device_type,
            "status": getattr(device, "status", "OFFLINE")
        }

        if hasattr(device, "interfaces"):
            result["interfaces"] = [ self._serialize_interface(interface) for interface in device.interfaces ]
        elif hasattr(device, "ports"):
            result["interfaces"] = [ self._serialize_interface(port) for port in device.ports.values() ]

        if hasattr(device, "mac_table"):
            result["mac_table"] = { mac: port for mac, port in device.mac_table.items() }

        if hasattr(device, "routes"):
            result["routes"] = [
                {
                    "destination": str(r["destination"]),
                    "interface": getattr(r["interface"], "name", None),
                    "next_hop": r["next_hop"]
                }
                for r in device.routes
            ]

        return result

    def _serialize_interface(self, interface):
        name = getattr(interface, "name", None)
        if name is None and hasattr(interface, "port_number"):
            name = f"Port-{interface.port_number}"

        result = {
            "name": name,
            "mac": (
                str(interface.mac)
                if getattr( interface, "mac", None ) is not None else None
            ),
            "ip": (
                str(interface.ip)
                if getattr( interface, "ip", None ) is not None else None
            ),
            "subnet": (
                str(interface.subnet)
                if getattr( interface, "subnet", None ) is not None else None
            ),
            "connected": (
                getattr( interface, "link", None ) is not None ),
            "status": getattr(interface, "status", "up")
        }
        
        if hasattr(interface, "port_number"):
            result["port_number"] = interface.port_number
            result["mode"] = getattr(interface, "mode", "access").upper()
            
        if getattr(interface, "link", None) is not None:
            other = interface.link.endpointB if interface.link.endpointA == interface else interface.link.endpointA
            result["connected_to"] = self._endpoint_name(other)
            
        return result

    def _serialize_link(self, link):

        return {
            "endpoint_a": self._endpoint_name( link.endpointA ),

            "endpoint_b": self._endpoint_name( link.endpointB )
        }

    @staticmethod
    def _endpoint_name(endpoint):

        owner = getattr( endpoint, "owner", None )

        if owner is not None:
            return owner.name

        switch = getattr( endpoint, "switch", None)

        if switch is not None:
            return switch.name

        return getattr( endpoint, "name", str(endpoint))

    def _serialize_service(self, service):
        return {
            "name": service.name,
            "protocol": service.protocol,
            "port": service.port,
            "status": getattr(service, "status", "stopped")
        }

    def _serialize(self, value):

        if value is None:
            return None

        if isinstance( value, (str, int, float, bool)):
            return value

        if isinstance(value, dict):
            return {
                str(key): self._serialize(item)
                for key, item in value.items()
            }

        if isinstance( value, (list, tuple, set) ):
            return [ self._serialize(item) for item in value ]

        if value.__class__.__name__ == "Service":
            return self._serialize_service(value)

        if hasattr(value, "value"):
            return value.value

        if hasattr(value, "name"):
            return value.name

        return str(value)