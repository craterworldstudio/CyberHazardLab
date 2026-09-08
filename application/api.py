class API:

    def __init__(self, ntm, ncm, state_manager):
        self.ntm = ntm
        self.ncm = ncm
        self.state_manager = state_manager

    # ========================================================
    # REQUEST DISPATCH
    # ========================================================

    def handle(self, method, path, body=None):
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

        raise ValueError(
            f"Unknown API manager: {manager}"
        )

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
            method == "POST" and len(resource) == 2
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

        if hasattr(value, "value"):
            return value.value

        if hasattr(value, "name"):
            return value.name

        return str(value)