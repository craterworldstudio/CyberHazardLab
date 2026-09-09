import json
from pathlib import Path


class StateManager:

    def __init__(self, simulation, path="simulation_state.json"):
        self.simulation = simulation
        self.path = Path(path)

        self.reset()

    # ========================================================
    # FILE MANAGEMENT
    # ========================================================

    def exists(self):
        return self.path.exists()

    def save(self, layout=None):
        if layout is None:
            # Try to preserve existing layout
            existing = self.load()
            if existing and "layout" in existing:
                layout = existing["layout"]
            else:
                layout = {}

        state = {
            "version": 1,
            "simulation": self.serialize_simulation(),
            "layout": layout
        }

        self.path.write_text(
            json.dumps(
                state,
                indent=4
            ),
            encoding="utf-8"
        )

    def load(self):
        if not self.exists():
            return None

        return json.loads(
            self.path.read_text(
                encoding="utf-8"
            )
        )



    def reset(self):
        state = {
            "version": 1,
            "simulation": {
                "devices": [],
                "links": [],
                "interfaces": {},
                "subnets": {},
                "routes": {},
                "services": {}
            },
            "layout": {}
        }

        self.path.write_text(
            json.dumps(
                state,
                indent=4
            ),
            encoding="utf-8"
        )

    # ========================================================
    # SERIALIZATION
    # ========================================================

    def serialize_simulation(self):
        return {
            "devices": self.serialize_devices(),
            "links": self.serialize_links(),
            "interfaces": self.serialize_interfaces(),
            "subnets": self.serialize_subnets(),
            "routes": self.serialize_routes(),
            "services": self.serialize_services()
        }

    def serialize_devices(self):
        devices = []

        for host in self.simulation.hosts.values():
            devices.append({
                "name": host.name,
                "type": host.device_type.value
            })

        for switch in self.simulation.switches.values():
            devices.append({
                "name": switch.name,
                "type": "switch"
            })

        for router in self.simulation.routers.values():
            devices.append({
                "name": router.name,
                "type": "router"
            })

        return devices

    def serialize_links(self):
        links = []

        for link in self.simulation.network.links:

            endpoint_a = self.endpoint_name(
                link.endpointA
            )

            endpoint_b = self.endpoint_name(
                link.endpointB
            )

            links.append({
                "endpoint_a": endpoint_a,
                "endpoint_b": endpoint_b
            })

        return links

    def serialize_interfaces(self):
        interfaces = {}

        for device in self.all_devices():

            if not hasattr(device, "interfaces"):
                continue

            interfaces[device.name] = []

            for interface in device.interfaces:

                interfaces[device.name].append({
                    "name": interface.name,
                    "mac": (
                        str(interface.mac)
                        if interface.mac is not None
                        else None
                    ),
                    "ip": (
                        str(interface.ip)
                        if interface.ip is not None
                        else None
                    ),
                    "subnet": (
                        str(interface.subnet)
                        if interface.subnet is not None
                        else None
                    )
                })

        return interfaces

    def serialize_subnets(self):
        return self.serialize_value(
            self.simulation.network.subnets
        )

    def serialize_routes(self):
        routes = {}

        for router in self.simulation.routers.values():

            router_routes = getattr(
                router,
                "routes",
                None
            )

            if router_routes is not None:
                routes[router.name] = self.serialize_value(
                    router_routes
                )

        return routes

    def serialize_services(self):
        services = {}

        for host in self.simulation.hosts.values():

            if not host.services:
                continue

            services[host.name] = []
            for svc in host.services:
                services[host.name].append({
                    "name": svc.name,
                    "protocol": svc.protocol,
                    "port": svc.port,
                    "status": svc.status
                })

        return services

    # ========================================================
    # HELPERS
    # ========================================================

    def all_devices(self):
        return [
            *self.simulation.hosts.values(),
            *self.simulation.switches.values(),
            *self.simulation.routers.values()
        ]

    @staticmethod
    def endpoint_name(endpoint):

        owner = getattr(
            endpoint,
            "owner",
            None
        )

        if owner is not None:
            return owner.name

        switch = getattr(
            endpoint,
            "switch",
            None
        )

        if switch is not None:
            return switch.name

        return getattr(
            endpoint,
            "name",
            str(endpoint)
        )

    def serialize_value(self, value):

        if value is None:
            return None

        if isinstance(
            value,
            (str, int, float, bool)
        ):
            return value

        if isinstance(value, dict):
            return {
                str(key): self.serialize_value(item)
                for key, item in value.items()
            }

        if isinstance(
            value,
            (list, tuple, set)
        ):
            return [
                self.serialize_value(item)
                for item in value
            ]

        if hasattr(value, "value"):
            return value.value

        if hasattr(value, "name"):
            return value.name

        if hasattr(value, "__dict__"):
            return {
                key: self.serialize_value(item)
                for key, item in value.__dict__.items()
                if not key.startswith("_")
            }

        return str(value)