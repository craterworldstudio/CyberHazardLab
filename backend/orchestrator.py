import ipaddress
import time
import threading
from typing import Any

from backend.core.host import Host
from backend.core.interface import NetworkInterface
from backend.core.mac import generate_mac
from backend.core.service import Service
from backend.core.device import DeviceType
from backend.core.event import Event
from backend.network.network import Network
from backend.network.dhcp import DHCP
from backend.network.switch import Switch
from backend.network.router import Router
from backend.network.link import Link
from backend.network.packet import Packet, ICMPPacket

class Simulation:
    def __init__(self, name="Network Simulation"):
        self.name = name
        self.network = Network(name)
        self.network.orchestrator = self
        self.dhcp = DHCP(self.network)

        self.hosts: dict[str, Host] = {}
        self.switches: dict[str, Switch] = {}
        self.routers: dict[str, Router] = {}

        self.is_running: bool = False
        self.settings: dict = {"auto_routes": True, "auto_mac_learning": True}
        self._tick_thread: threading.Thread | None = None
        
        self.network.on_event = self._handle_network_event

    def _handle_network_event(self, event: Event):
        if event.severity in ["HIGH", "ERROR"]:
            dev_name = None
            if hasattr(event, "metadata") and event.metadata:
                dev_name = event.metadata.get("router") or event.metadata.get("host") or event.metadata.get("switch")
            if dev_name:
                dev = self.get_device(dev_name)
                if dev:
                    dev.status = "ERROR"

    # ========================================================
    # DEVICE LOOKUP & HELPERS
    # ========================================================

    def get_host(self, name: str):
        if name in self.hosts:
            return self.hosts[name]
        if name in self.routers:
            return self.routers[name]
        return None

    def get_device(self, name: str):
        if name in self.hosts:
            return self.hosts[name]
        if name in self.routers:
            return self.routers[name]
        if name in self.switches:
            return self.switches[name]
        return None

    def get_device_type(self, value_str: str) -> DeviceType:
        cleaned = str(value_str).lower().strip()
        for member in DeviceType:
            if member.value == cleaned:
                return member
        return DeviceType.OTHER

    # ========================================================
    # DEVICE LIFECYCLE
    # ========================================================

    def add_host(self, name: str, *args, **kwargs) -> Host:
        if name in self.hosts or name in self.routers or name in self.switches:
            raise ValueError(f"Device '{name}' already exists.")
        
        device_type = kwargs.get("device_type") or kwargs.get("device")
        if not device_type and args:
            for a in args:
                if isinstance(a, DeviceType):
                    device_type = a
                    break
                elif isinstance(a, str) and not ("." in a or "/" in a):
                    device_type = self.get_device_type(a)
                    break

        if not device_type:
            device_type = DeviceType.PC
        elif isinstance(device_type, str):
            device_type = self.get_device_type(device_type)

        host = Host(name=name, device_type=device_type, network=self.network)
        self.hosts[name] = host
        self.network.add_host(host)
        return host

    def remove_host(self, name: str):
        host = self.hosts.pop(name, None)
        if not host:
            raise ValueError(f"Host '{name}' not found.")
        # Disconnect all links
        for link in list(self.network.links):
            if any(link.endpointA == i or link.endpointB == i for i in host.interfaces):
                self.disconnect(link)
        self.network.hosts.pop(name, None)
        return host

    def add_router(self, name: str) -> Router:
        if name in self.hosts or name in self.routers or name in self.switches:
            raise ValueError(f"Device '{name}' already exists.")
        router = Router(name=name, network=self.network)
        self.routers[name] = router
        self.network.add_host(router)
        return router

    def remove_router(self, name: str):
        router = self.routers.pop(name, None)
        if not router:
            raise ValueError(f"Router '{name}' not found.")
        for link in list(self.network.links):
            if any(link.endpointA == i or link.endpointB == i for i in router.interfaces):
                self.disconnect(link)
        self.network.hosts.pop(name, None)
        return router

    def add_switch(self, name: str) -> Switch:
        if name in self.hosts or name in self.routers or name in self.switches:
            raise ValueError(f"Device '{name}' already exists.")
        switch = Switch(name=name, network=self.network)
        self.switches[name] = switch
        return switch

    def remove_switch(self, name: str):
        switch = self.switches.pop(name, None)
        if not switch:
            raise ValueError(f"Switch '{name}' not found.")
        for link in list(self.network.links):
            if any(link.endpointA == p or link.endpointB == p for p in switch.ports.values()):
                self.disconnect(link)
        return switch

    # ========================================================
    # INTERFACE LIFECYCLE
    # ========================================================

    def add_host_interface(self, host, name=None, mac=None):
        if isinstance(host, str):
            host = self.get_host(host)
        if not host:
            raise ValueError("Invalid host specified.")

        if name is None:
            name = f"eth{len(host.interfaces)}"
        for existing in host.interfaces:
            if existing.name == name:
                raise ValueError(f"Interface '{name}' already exists on {host.name}")

        mac = mac or generate_mac()
        intf = NetworkInterface(name=name, mac=mac, owner=host, ip="0.0.0.0", subnet="0.0.0.0/0")
        intf.attach_network(self.network)
        host.add_interface(intf)
        return intf

    def remove_host_interface(self, host, intf_or_name):
        if isinstance(host, str):
            host = self.get_host(host)
        intf_name = getattr(intf_or_name, "name", intf_or_name)
        intf = host.get_interface(intf_name)
        if not intf:
            raise ValueError(f"Interface '{intf_name}' not found on {host.name}")
        if intf.link:
            self.disconnect(intf.link)
        return host.remove_interface(intf_name)

    def add_router_interface(self, router, name=None, mac=None):
        if isinstance(router, str):
            router = self.routers.get(router)
        if not router:
            raise ValueError("Invalid router specified.")

        if name is None:
            name = f"eth{len(router.interfaces)}"
        for existing in router.interfaces:
            if existing.name == name:
                raise ValueError(f"Interface '{name}' already exists on {router.name}")

        mac = mac or generate_mac()
        intf = NetworkInterface(name=name, mac=mac, owner=router, ip="0.0.0.0", subnet="0.0.0.0/0")
        intf.attach_network(self.network)
        router.add_interface(intf)
        return intf

    def remove_router_interface(self, router, intf_name: str):
        return self.remove_host_interface(router, intf_name)

    def configure_router_interface(self, router, interface, ip=None, subnet=None):
        if isinstance(router, str):
            router = self.routers.get(router)
        if isinstance(interface, str):
            interface = router.get_interface(interface)
        if router and interface:
            router.update_intf(interface, ip=ip, subnet=subnet)
        return interface

    # ========================================================
    # TOPOLOGY CONNECTIONS
    # ========================================================

    def connect_interfaces(self, interface_a: NetworkInterface, interface_b: NetworkInterface) -> Link:
        link = Link(interface_a, interface_b)
        self.network.add_link(link)
        interface_a.connect_link(link)
        interface_b.connect_link(link)
        return link

    def connect_host_to_switch(self, host, switch, host_intf=None, port_num=None) -> Link:
        if isinstance(host, str):
            host = self.get_host(host)
        if isinstance(switch, str):
            switch = self.switches[switch]
        return switch.connect(host, host_intf.name if host_intf else "eth0")

    def connect_switch_to_router(self, switch, router_interface) -> Link:
        if isinstance(switch, str):
            switch = self.switches[switch]
        return switch.connect_router(router_interface)

    def connect_switches(self, switch_a, switch_b, port_a=None, port_b=None) -> Link:
        if isinstance(switch_a, str):
            switch_a = self.switches[switch_a]
        if isinstance(switch_b, str):
            switch_b = self.switches[switch_b]
        return switch_a.connect_switch(switch_b)

    def disconnect(self, link: Link):
        if link not in self.network.links:
            return link
        ep_a, ep_b = link.endpointA, link.endpointB
        if hasattr(ep_a, "link") and ep_a.link is link:
            ep_a.link = None
        if hasattr(ep_b, "link") and ep_b.link is link:
            ep_b.link = None
        self.network.links.remove(link)
        return link

    def get_links(self) -> list[Link]:
        return list(self.network.links)

    # ========================================================
    # SERVICES
    # ========================================================

    def add_service(self, host, name: str, protocol: str, port: int, status="stopped", config=None) -> Service:
        if isinstance(host, str):
            host = self.get_host(host)
        if not host:
            raise ValueError("Device not found")
        service = Service(name=name, protocol=protocol, port=port, status=status, config=config or {})
        self.network.add_service(host, service)
        return service

    def start_service(self, host, service_name: str, force: bool = False):
        if isinstance(host, str):
            host = self.get_host(host)
        self.network.start_service(host, service_name, force=force)

    def stop_service(self, host, service_name: str):
        if isinstance(host, str):
            host = self.get_host(host)
        self.network.stop_services(host, service_name)

    def remove_service(self, host, service_name: str):
        if isinstance(host, str):
            host = self.get_host(host)
        self.network.remove_service(host, service_name)

    def add_subnet(self, subnet: str, gateway: str | None = None):
        return self.network.add_subnet(subnet, gateway)

    def add_dhcp_scope(self, subnet, start_ip, end_ip, gateway, dns="8.8.8.8", lease_time=120):
        return self.dhcp.add_scope(subnet, start_ip, end_ip, gateway, dns, lease_time)

    # ========================================================
    # SIMULATION LIFECYCLE & TICK LOOP
    # ========================================================

    def run(self):
        if self.is_running:
            return
        self.is_running = True

        # 1. Provision default routes for hosts connected to routers
        for host in self.hosts.values():
            has_default = any(str(r["destination"]) == "0.0.0.0/0" for r in host.routes)
            if not has_default:
                for intf in host.interfaces:
                    if intf.ip and intf.ip != "0.0.0.0" and intf.subnet:
                        gw = None
                        for router in self.routers.values():
                            for r_intf in router.interfaces:
                                if r_intf.subnet == intf.subnet and r_intf.ip and r_intf.ip != "0.0.0.0":
                                    gw = r_intf.ip
                                    break
                            if gw:
                                break
                        if gw:
                            host.add_route("0.0.0.0/0", intf, next_hop=gw)
                            break

        # 2. Provision DHCP scopes for subnets if not already configured
        for router in self.routers.values():
            for r_intf in router.interfaces:
                if r_intf.subnet and r_intf.subnet not in ("0.0.0.0/0", "0.0.0.0"):
                    self.dhcp.auto_provision_scope(r_intf.subnet, default_gateway=r_intf.ip)

        # 3. Bring devices online and start enabled services
        now = time.time()
        all_nodes = list(self.hosts.values()) + list(self.routers.values())
        for node in all_nodes:
            node.status = "ONLINE"
            node.boot_time = now
            for s in node.services:
                if getattr(s, "enabled", True):
                    self.start_service(node, s.name, force=True)

        for switch in self.switches.values():
            switch.status = "ONLINE"
            switch.boot_time = now

        # 4. Start tick loop
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._tick_thread.start()

    def _tick_loop(self):
        while self.is_running:
            for host in list(self.hosts.values()):
                host.update()
            for router in list(self.routers.values()):
                router.update()
            for switch in list(self.switches.values()):
                switch.update()
            time.sleep(0.01)

    def stop(self):
        self.is_running = False
        all_nodes = list(self.hosts.values()) + list(self.routers.values())
        for node in all_nodes:
            node.status = "OFFLINE"
            node.boot_time = None
            for s in node.services:
                if s.status == "running":
                    self.stop_service(node, s.name)

        for switch in self.switches.values():
            switch.status = "OFFLINE"
            switch.boot_time = None

    def validate(self):
        updated = []
        for host in self.hosts.values():
            connected = any(i.link is not None for i in host.interfaces)
            old_status = host.status
            host.status = ("ONLINE" if self.is_running else "OFFLINE") if connected else "ERROR"
            if old_status != host.status:
                updated.append(host.name)
        return updated

    # ========================================================
    # ICMP PING HELPER
    # ========================================================

    def ping(self, source, destination_ip: str, payload="ping", ttl=64):
        if isinstance(source, str):
            source = self.get_host(source)
        if not source or not source.interfaces:
            raise ValueError("Source device has no interfaces.")

        source.last_icmp_result = None
        intf = source.interfaces[0]

        icmp = ICMPPacket(type="ECHO_REQUEST", code=0, payload=payload)
        packet = Packet(
            source_ip=intf.ip,
            destination_ip=destination_ip,
            protocol="ICMP",
            payload=icmp,
            ttl=ttl
        )
        source.send_ip_packet(packet, out_interface=intf)
        # Wait up to 200ms for tick-based delivery and ICMP reply
        start_wait = time.time()
        while time.time() - start_wait < 0.2:
            if source.last_icmp_result is not None:
                break
            time.sleep(0.01)
        return source.last_icmp_result
