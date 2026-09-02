from backend.core.host import Host
from backend.core.service import Service
from backend.network.network import Network
from backend.network.dhcp import DHCP
from backend.network.packet import Packet
from backend.network.switch import Switch
from backend.network.router import Router
from backend.network.link import Link
from backend.network.tcp import TCPConnection
from backend.network.udp import UDPConnection
from backend.core.device import DeviceType
from backend.network.packet import *


class Simulation:

    def __init__(self, name="Network Simulation"):

        self.name = name

        self.network = Network(name)

        self.dhcp = DHCP(self.network)

        self.hosts = {}
        self.switches = {}
        self.routers = {}

        self.tcp_connections = {}
        self.udp_connections = {}

    # ========================================================
    # TOPOLOGY
    # ========================================================

    def add_subnet(self, subnet, gateway):

        self.network.add_subnet(
            subnet,
            gateway
        )

    def add_dhcp_scope( self, subnet, start_ip, end_ip, gateway):

        self.dhcp.add_scope(
            subnet=subnet,
            start_ip=start_ip,
            end_ip=end_ip,
            gateway=gateway
        )

    # ========================================================
    # HOSTS
    # ========================================================

    def get_device_type(self, value_str: str) -> DeviceType:
        """
        Takes a string input and returns the corresponding HostDeviceType Enum.
        Returns HostDeviceType.OTHER if the string does not match any valid enum value.
        """
        # Clean the input string to handle case sensitivity and whitespace
        cleaned_input = str(value_str).lower().strip()

        try:
            # Looks up the enum member by its exact string value
            return DeviceType(cleaned_input)
        except ValueError:
            # Fallback if the string isn't recognized
            return DeviceType.OTHER
        

    def add_host( self, name, subnet=None, device:DeviceType = DeviceType.PC):

        host = Host(name, device_type=device, network=self.network)

        host.interfaces[0].attach_network(
            self.network
        )

        if subnet is not None:

            self.dhcp.req_ip(
                host.interfaces[0],
                subnet
            )

        self.network.add_host(host)

        self.hosts[name] = host

        return host

    def get_host(self, name):

        if name not in self.hosts:
            raise ValueError(
                f"Unknown host: {name}"
            )

        return self.hosts[name]

    # ========================================================
    # SERVICES
    # ========================================================

    def add_service( self, host, name, protocol, port, status="stopped"):

        if isinstance(host, str):
            host = self.get_host(host)

        service = Service(
            name=name,
            protocol=protocol,
            port=port,
            status=status
        )

        self.network.add_service(
            host,
            service
        )

        return service

    def start_service( self, host, service_name):

        if isinstance(host, str):
            host = self.get_host(host)

        self.network.start_service(
            host,
            service_name
        )

    def stop_service( self, host, service_name):

        if isinstance(host, str):
            host = self.get_host(host)

        self.network.stop_services(
            host,
            service_name
        )

    # ========================================================
    # SWITCHES
    # ========================================================

    def add_switch(self, name):

        switch = Switch(
            name,
            self.network
        )

        self.switches[name] = switch

        return switch

    def connect_host_to_switch( self, host, switch):

        if isinstance(host, str):
            host = self.get_host(host)

        if isinstance(switch, str):
            switch = self.switches[switch]

        switch.connect(host)

    # ========================================================
    # ROUTERS
    # ========================================================

    def add_router(self, name):

        router = Router(
            name,
            self.network
        )

        self.routers[name] = router

        return router

    def configure_router_interface( self, router, interface, ip, subnet):

        if isinstance(router, str):
            router = self.routers[router]

        router.update_intf(
            interface,
            ip=ip,
            subnet=subnet
        )

    def connect_router_interface( self, switch, router_interface ):

        if isinstance(switch, str):
            switch = self.switches[switch]

        switch.connect_router(
            router_interface
        )

    def connect_router_interfaces( self, interface_a, interface_b ):

        link = Link(
            interface_a,
            interface_b
        )

        interface_a.connect_link(link)
        interface_b.connect_link(link)

    def add_route( self, router, destination, interface, next_hop=None ):

        if isinstance(router, str):
            router = self.routers[router]

        router.add_route(
            destination=destination,
            interface=interface,
            next_hop=next_hop
        )

    # ========================================================
    # PACKET HELPERS
    # ========================================================

    @staticmethod
    def tcp_to_ip_packet( source_interface, destination_ip, tcp_packet, ttl=64):

        return Packet(
            source_ip=source_interface.ip,
            destination_ip=destination_ip,
            protocol="TCP",
            ttl = ttl,
            payload=tcp_packet
        )

    @staticmethod
    def udp_to_ip_packet( source_interface, destination_ip, udp_packet, ttl=64 ):

        return Packet(
            source_ip=source_interface.ip,
            destination_ip=destination_ip,
            protocol="UDP",
            ttl = ttl,
            payload=udp_packet
        )

    @staticmethod
    def icmp_to_ip_packet( source_interface, destination_ip, icmp_packet, ttl=64 ):

        return Packet(
            source_ip=source_interface.ip,
            destination_ip=destination_ip,
            protocol="ICMP",
            ttl = ttl,
            payload=icmp_packet
        )
    # ========================================================
    # TCP
    # ========================================================

    def create_tcp_connection( self, source, source_port, destination, destination_port ):

        if isinstance(source, str):
            source = self.get_host(source)

        if isinstance(destination, str):
            destination = self.get_host(destination)

        existing = self.get_tcp_connection(
            source,
            source_port,
            destination,
            destination_port
        )
        
        if existing is not None:
            return existing

        connection = TCPConnection(
            local_ip=source.get_ip(),
            local_port=source_port,
            remote_ip=destination.get_ip(),
            remote_port=destination_port,
            network=self.network
        )

        key = (
            connection.remote_ip,
            connection.remote_port,
            connection.local_ip,
            connection.local_port
        )

        source.tcp_connections[key] = connection

        self.tcp_connections[key] = connection

        return connection

    def remove_tcp_connection(self, connection):

        key = (
            connection.remote_ip,
            connection.remote_port,
            connection.local_ip,
            connection.local_port
        )

        self.tcp_connections.pop(key, None)

        host = self.get_host_by_ip(connection.local_ip)

        host.tcp_connections.pop(key, None)

    def tcp_connect( self, connection ):

        packet = connection.connect()

        ip_packet = self.tcp_to_ip_packet(
            self.get_host_by_ip(connection.local_ip).interfaces[0],
            connection.remote_ip,
            packet
        )

        return self.get_host_by_ip(
            connection.local_ip
        ).interfaces[0].send_ip_packet(
            ip_packet
        )

    def get_host_by_ip(self, ip):

        if ip not in self.network.hosts:
            raise ValueError(
                f"No host with IP {ip}"
            )

        return self.network.hosts[ip]

    # ========================================================
    # UDP
    # ========================================================

    def create_udp_connection( self, source, source_port, destination, destination_port ):

        if isinstance(source, str):
            source = self.get_host(source)

        if isinstance(destination, str):
            destination = self.get_host(destination)

        existing = self.get_udp_connection(
            source,
            source_port,
            destination,
            destination_port
        )
        
        if existing is not None:
            return existing

        connection = UDPConnection(
            local_ip=source.get_ip(),
            local_port=source_port,
            remote_ip=destination.get_ip(),
            remote_port=destination_port,
            network=self.network
        )

        key = (
            connection.remote_ip,
            connection.remote_port,
            connection.local_ip,
            connection.local_port
        )

        self.udp_connections[key] = connection

        return connection

    def remove_udp_connection(self, connection):

        key = (
            connection.remote_ip,
            connection.remote_port,
            connection.local_ip,
            connection.local_port
        )

        self.udp_connections.pop(key, None)

        host = self.get_host_by_ip(connection.local_ip)

        host.udp_connections.pop(key, None)

    def udp_send( self, connection, data ):

        packet = connection.send(data)

        source_host = self.get_host_by_ip(
            connection.local_ip
        )

        ip_packet = self.udp_to_ip_packet(
            source_host.interfaces[0],
            connection.remote_ip,
            packet
        )

        return source_host.interfaces[0].send_ip_packet(
            ip_packet
        )

    # ========================================================
    # CONNECTION MANAGEMENT
    # ========================================================

    def get_tcp_connection( self, source, source_port, destination, destination_port ):
        if isinstance(source, str):
            source = self.get_host(source)

        if isinstance(destination, str):
            destination = self.get_host(destination)

        key = (
            destination.get_ip(),
            destination_port,
            source.get_ip(),
            source_port
        )

        return self.tcp_connections.get(key)

    def get_udp_connection( self, source, source_port, destination, destination_port ):
        if isinstance(source, str):
            source = self.get_host(source)

        if isinstance(destination, str):
            destination = self.get_host(destination)

        key = (
            destination.get_ip(),
            destination_port,
            source.get_ip(),
            source_port
        )

        return self.udp_connections.get(key)

    def get_active_connections(self):

        return {
            "tcp": [
                {
                    "local": (
                        connection.local_ip,
                        connection.local_port
                    ),
                    "remote": (
                        connection.remote_ip,
                        connection.remote_port
                    ),
                    "state": connection.state.value
                }
                for connection in self.tcp_connections.values()
            ],

            "udp": [
                {
                    "local": (
                        connection.local_ip,
                        connection.local_port
                    ),
                    "remote": (
                        connection.remote_ip,
                        connection.remote_port
                    )
                }
                for connection in self.udp_connections.values()
            ]
        }

    # ========================================================
    # GENERIC PACKET SENDING
    # ========================================================
    def ping(self, source, destination_ip, payload="ping", ttl=64):

        if isinstance(source, str):
            source = self.get_host(source)

        interface = source.interfaces[0]
        source.last_icmp_result = None


        request = ICMPPacket(
            type="ECHO_REQUEST",
            code=0,
            payload=payload
        )

        packet = self.icmp_to_ip_packet(
            interface,
            destination_ip,
            request,
            ttl=ttl
        )
        interface.send_ip_packet(packet)
        return source.last_icmp_result

    def send_packet( self, source, destination_ip, packet ):

        if isinstance(source, str):
            source = self.get_host(source)

        ip_packet = Packet(
            source_ip=source.get_ip(),
            destination_ip=destination_ip,
            protocol=packet.protocol,
            payload=packet
        )

        return source.interfaces[0].send_ip_packet(
            ip_packet
        )

    def traceroute(self, source, destination_ip, max_hops=30):

        if isinstance(source, str):
            source = self.get_host(source)

        hops = []

        for ttl in range(1, max_hops + 1):

            result = self.ping(
                source=source,
                destination_ip=destination_ip,
                ttl=ttl
            )

            if result is None:
                hops.append({
                    "ttl": ttl,
                    "address": None,
                    "type": "TIMEOUT"
                })

                continue

            if result["type"] == "TIME_EXCEEDED":

                hops.append({
                    "ttl": ttl,
                    "address": result["source"],
                    "type": "TIME_EXCEEDED"
                })

                continue

            if result["type"] == "ECHO_REPLY":

                hops.append({
                    "ttl": ttl,
                    "address": result["source"],
                    "type": "ECHO_REPLY"
                })

                break

            hops.append({
                "ttl": ttl,
                "address": result["source"],
                "type": result["type"]
            })

            break

        return hops

    # ========================================================
    # TIME
    # ========================================================

    def tick(self, seconds):

        if seconds < 0:
            raise ValueError(
                "seconds cannot be negative"
            )

        for connection in list(self.tcp_connections.values()):

            connection.tick(seconds)

            if connection.state.value == "CLOSED":
                self.remove_tcp_connection(connection)

    # ========================================================
    # TELEMETRY
    # ========================================================

    def get_events(self):

        return self.network.events

    def clear_events(self):

        self.network.events.clear()

    # ========================================================
    # SIMULATION STATE
    # ========================================================

    def get_state(self):

        return {
            "name": self.name,

            "hosts": [
                {
                    "name": host.name,
                    
                    "ip": host.get_ip(),
                    "mac": host.get_mac(),
                    "device_type": host.device_type.name,
                    "services": [
                        {
                            "name": service.name,
                            "protocol": service.protocol,
                            "port": service.port,
                            "status": service.status
                        }

                        for service in host.services
                    ]
                }

                for host in self.hosts.values()
            ],

            "tcp_connections": [
                {
                    "local": (
                        connection.local_ip,
                        connection.local_port
                    ),

                    "remote": (
                        connection.remote_ip,
                        connection.remote_port
                    ),

                    "state": connection.state.value
                }

                for connection in self.tcp_connections.values()
            ],

            "udp_connections": [
                {
                    "local": (
                        connection.local_ip,
                        connection.local_port
                    ),

                    "remote": (
                        connection.remote_ip,
                        connection.remote_port
                    )
                }

                for connection in self.udp_connections.values()
            ]
        }


    
