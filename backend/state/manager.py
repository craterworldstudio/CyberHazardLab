import json
from pathlib import Path


class StateManager:

    def __init__(self, simulation, path=None):
        self.simulation = simulation
        if path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.path = base_dir / "simulation_state.json"
        else:
            self.path = Path(path)

        #self.reset()

    # ========================================================
    # FILE MANAGEMENT
    # ========================================================

    def exists(self):
        return self.path.exists()

    def save(self, file_path=None, layout=None):
        if file_path is not None:
            self.path = Path(file_path)

        # Safely read current file state to preserve layout & renames
        current_layout = {}
        saved_renames = {}
        if self.exists():
            try:
                raw_data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw_data, dict):
                    if isinstance(raw_data.get("layout"), dict):
                        current_layout = dict(raw_data["layout"])
                    if isinstance(raw_data.get("renames"), dict):
                        saved_renames = dict(raw_data["renames"])
            except Exception:
                pass

        sim_renames = getattr(self.simulation, "rename_map", {})
        saved_renames.update(sim_renames)

        # Flatten transitive aliases: if A->B and B->C exists, make A->C directly.
        # Prevents stale intermediate names from persisting across multiple renames.
        changed = True
        while changed:
            changed = False
            for k, v in list(saved_renames.items()):
                if v in saved_renames and saved_renames[v] != v:
                    saved_renames[k] = saved_renames[v]
                    changed = True

        # Remove self-referential entries (A->A)
        saved_renames = {k: v for k, v in saved_renames.items() if k != v}

        if not layout:
            layout = dict(current_layout)
        else:
            layout = dict(layout)
            # Merge with existing layout so unmentioned active devices never lose coordinates!
            for k, v in current_layout.items():
                if k in saved_renames or k in sim_renames:
                    continue
                if k not in layout and v:
                    layout[k] = v

        # Migrate layout keys if any device was renamed, and prune old names
        for old_n, new_n in saved_renames.items():
            if old_n in layout:
                if new_n not in layout:
                    layout[new_n] = layout[old_n]
                layout.pop(old_n, None)

        # Update simulation rename_map with all saved renames
        if hasattr(self.simulation, "rename_map"):
            self.simulation.rename_map.update(saved_renames)

        state = {
            "version": 1,
            "simulation": self.serialize_simulation(),
            "layout": layout,
            "renames": saved_renames
        }

        self.path.write_text(
            json.dumps(
                state,
                indent=4
            ),
            encoding="utf-8"
        )

    def rename_device(self, old_name: str, new_name: str):
        current = self.load()
        layout = {}
        if current and "layout" in current and isinstance(current["layout"], dict):
            layout = dict(current["layout"])
            if old_name in layout:
                layout[new_name] = layout.pop(old_name)
        self.save(layout=layout)

    def load(self):
        if not self.exists():
            return None

        data = json.loads(
            self.path.read_text(
                encoding="utf-8"
            )
        )
        if isinstance(data, dict) and "renames" in data and isinstance(data["renames"], dict):
            if not hasattr(self.simulation, "rename_map") or self.simulation.rename_map is None:
                self.simulation.rename_map = {}
            self.simulation.rename_map.update(data["renames"])
        return data



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
            "mac_tables": self.serialize_mac_tables(),
            "arp_caches": self.serialize_arp_caches(),
            "services": self.serialize_services()
        }

    def serialize_devices(self):
        devices = []

        for host in self.simulation.hosts.values():
            d = {
                "name": host.name,
                "type": host.device_type.value
            }
            if getattr(host, "default_gateway", None):
                d["default_gateway"] = host.default_gateway
            devices.append(d)

        for switch in self.simulation.switches.values():
            devices.append({
                "name": switch.name,
                "type": "switch",
                "auto_mac_learning": getattr(switch, "auto_mac_learning", "inherit"),
                "mac_aging_time": getattr(switch, "mac_aging_time", 300),
                "stp_enabled": getattr(switch, "stp_enabled", False)
            })

        for router in self.simulation.routers.values():
            d = {
                "name": router.name,
                "type": "router",
                "ip_forwarding": getattr(router, "ip_forwarding", True),
                "auto_routes": getattr(router, "auto_routes", "inherit")
            }
            if getattr(router, "default_gateway", None):
                d["default_gateway"] = router.default_gateway
            devices.append(d)

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
                    ),
                    # Persist gateway from the owning node so it survives restart
                    "gateway": getattr(device, "default_gateway", None)
                })

        return interfaces


    def serialize_subnets(self):
        return self.serialize_value(
            self.simulation.network.subnets
        )

    def serialize_routes(self):
        routes = {}
        for router in self.simulation.routers.values():
            router_routes = getattr(router, "routes", None)
            if router_routes is not None:
                serialized = []
                for r in router_routes:
                    serialized.append({
                        "destination": str(r["destination"]),
                        "interface": getattr(r["interface"], "name", None),
                        "next_hop": r["next_hop"]
                    })
                routes[router.name] = serialized
        return routes

    def serialize_mac_tables(self):
        macs = {}
        for switch in self.simulation.switches.values():
            if hasattr(switch, "mac_table") and switch.mac_table:
                macs[switch.name] = dict(switch.mac_table)
        return macs

    def serialize_arp_caches(self):
        arps = {}
        for device in self.all_devices():
            if not hasattr(device, "interfaces"): continue
            for intf in device.interfaces:
                if hasattr(intf, "arp") and intf.arp and intf.arp.cache:
                    if device.name not in arps:
                        arps[device.name] = {}
                    arps[device.name][intf.name] = dict(intf.arp.cache)
        return arps

    def serialize_services(self):
        services = {}

        all_nodes = list(self.simulation.hosts.values()) + list(self.simulation.routers.values())
        for node in all_nodes:
            if not getattr(node, "services", None):
                continue
            services[node.name] = []
            for svc in node.services:
                services[node.name].append({
                    "name": svc.name,
                    "protocol": svc.protocol,
                    "port": svc.port,
                    "status": svc.status,
                    "config": getattr(svc, "config", {})
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