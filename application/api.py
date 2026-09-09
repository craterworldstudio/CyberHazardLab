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
                from backend.core.event import Event
                event = Event(
                    type="SYSTEM_ERROR",
                    source="API",
                    destination="SYSTEM",
                    severity="HIGH",
                    metadata={"error": str(e), "path": path, "method": method}
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
            from backend.orchestrator import Simulation
            self.ntm.simulation = Simulation()
            self.ncm.simulation = self.ntm.simulation
            self.state_manager.simulation = self.ntm.simulation
            self.state_manager.reset()
            return {"status": "success"}

        if method == "GET" and resource == ["export"]:
            self.state_manager.save()
            return self.state_manager.load()

        if method == "POST" and resource == ["import"]:
            from backend.orchestrator import Simulation
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
                        self.ncm.update_interface(device_name, intf["name"], ip=intf.get("ip"), subnet=intf.get("subnet"))
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
                        self.ncm.add_service(device_name, s["name"], s["protocol"], s["port"], s.get("status", "stopped"))
                    except Exception:
                        pass
                        
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
            service = self.ncm.add_service(
                resource[1],
                body["name"],
                body["protocol"],
                int(body["port"])
            )
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

        # DELETE /api/ncm/subnets
        if (
            method == "DELETE"
            and resource == ["subnets"]
        ):

            result = self.ncm.remove_subnet(
                body["subnet"]
            )

            self.state_manager.save()
            return self._serialize(result)

        

        # POST /api/ncm/subnets
        if (
            method == "POST"
            and resource == ["subnets"]
        ):
            result = self.ncm.add_subnet(
                body["subnet"],
                body.get("gateway")
            )

            self.state_manager.save()

            return self._serialize(result)

        # GET /api/ncm/subnets
        if (
            method == "GET"
            and resource == ["subnets"]
        ):
            return self._serialize( self.ncm.get_subnets() )

        # GET /api/ncm/subnets/<network>
        if ( method == "GET" and len(resource) == 2 and resource[0] == "subnets" ):
            return self._serialize( self.ncm.get_subnet( resource[1] ) )

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

        return result

    def _serialize_interface(self, interface):

        return {
            "name": getattr( interface, "name", None ),

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
                getattr( interface, "link", None ) is not None )
        }

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