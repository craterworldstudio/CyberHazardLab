import ipaddress
import time
from typing import Any
from backend.core.event import Event
from backend.core.device import DeviceType
from backend.core.interface import NetworkInterface
from backend.core.mac import generate_mac
from backend.core.service import Service
from backend.network.arp import ARP
from backend.network.frame import EthernetFrame
from backend.network.packet import Packet, ARPPacket, ICMPPacket, UDPPacket, TCPPacket

class Node:
    """
    Unified Layer-3 network node base class for Hosts and Routers.
    Implements standard IP routing (FIB), ARP subsystem, and packet processing.
    """
    def __init__(self, name: str, device_type: DeviceType = DeviceType.OTHER, network: Any = None):
        self.name = name
        self.device_type = device_type
        self.network = network
        self.interfaces: list[NetworkInterface] = []
        self.routes: list[dict] = []
        self.services: list[Service] = []
        self.status: str = "OFFLINE"
        self.boot_time: float | None = None
        self.forwarding_enabled: bool = False
        self.default_gateway: str | None = None
        
        self.arp = ARP(self)
        self.tcp_connections: dict = {}
        self.udp_connections: dict = {}
        self.daemons: dict = {}
        self.last_icmp_result: dict | None = None

    # ========================================================
    # INTERFACE MANAGEMENT
    # ========================================================

    def add_interface(self, interface):
        if isinstance(interface, str):
            from backend.core.mac import generate_mac
            interface = NetworkInterface(
                name=interface,
                mac=generate_mac(),
                owner=self,
                ip="0.0.0.0",
                subnet="0.0.0.0/0"
            )
        interface.owner = self
        if self.network:
            interface.attach_network(self.network)
        self.interfaces.append(interface)
        
        # Install direct connected route if configured
        self._install_connected_route(interface)
        return interface

    def remove_interface(self, interface_name: str):
        intf = self.get_interface(interface_name)
        if intf:
            self._remove_connected_route(intf)
            self.interfaces.remove(intf)
            return intf
        return None

    def get_interface(self, interface_name: str) -> NetworkInterface | None:
        for intf in self.interfaces:
            if intf.name == interface_name:
                return intf
        return None

    def get_ip(self) -> str | None:
        for intf in self.interfaces:
            if intf.ip and intf.ip != "0.0.0.0":
                return intf.ip
        return self.interfaces[0].ip if self.interfaces else None

    def get_mac(self) -> str | None:
        return self.interfaces[0].mac if self.interfaces else None

    def update_intf(self, interface: NetworkInterface, ip: str | None = None, subnet: str | None = None):
        """Update interface IP and subnet, refreshing connected routes."""
        self._remove_connected_route(interface)
        
        if ip is not None:
            interface.ip = ip
        if subnet is not None:
            interface.subnet = subnet
        elif ip and ip != "0.0.0.0" and (not interface.subnet or interface.subnet in ("0.0.0.0/0", "0.0.0.0")):
            try:
                interface.subnet = str(ipaddress.ip_network(f"{ip}/24", strict=False))
            except Exception:
                pass
            
        self._install_connected_route(interface)

    # ========================================================
    # ROUTING TABLE (FIB)
    # ========================================================

    def _install_connected_route(self, interface: NetworkInterface):
        if not interface.ip or interface.ip == "0.0.0.0":
            return
        if not interface.subnet or interface.subnet in ("0.0.0.0/0", "0.0.0.0"):
            try:
                interface.subnet = str(ipaddress.ip_network(f"{interface.ip}/24", strict=False))
            except Exception:
                return
        try:
            net = ipaddress.ip_network(interface.subnet, strict=False)
            # Check if route already exists
            for r in self.routes:
                if r["destination"] == net and r["interface"] == interface:
                    return
            self.routes.append({
                "destination": net,
                "next_hop": None,
                "interface": interface
            })
        except Exception:
            pass

    def _remove_connected_route(self, interface: NetworkInterface):
        if not interface.subnet:
            return
        try:
            net = ipaddress.ip_network(interface.subnet, strict=False)
            self.routes = [
                r for r in self.routes
                if not (r["destination"] == net and r["interface"] == interface and r["next_hop"] is None)
            ]
        except Exception:
            pass

    def add_route(self, destination, interface: NetworkInterface, next_hop: str | None = None):
        dest_net = ipaddress.ip_network(destination, strict=False) if isinstance(destination, str) else destination
        # Remove any existing identical destination route
        self.routes = [r for r in self.routes if r["destination"] != dest_net]
        self.routes.append({
            "destination": dest_net,
            "next_hop": next_hop,
            "interface": interface
        })

    def remove_route(self, destination):
        dest_net = ipaddress.ip_network(destination, strict=False) if isinstance(destination, str) else destination
        self.routes = [r for r in self.routes if r["destination"] != dest_net]

    def lookup_route(self, destination_ip: str) -> dict | None:
        try:
            ip_obj = ipaddress.ip_address(destination_ip)
        except Exception:
            return None

        matching = [r for r in self.routes if ip_obj in r["destination"]]
        if not matching:
            return None
        # Longest Prefix Match
        return max(matching, key=lambda r: r["destination"].prefixlen)

    # ========================================================
    # LAYER-3 TRANSMISSION
    # ========================================================

    def send_ip_packet(self, packet: Packet, out_interface: NetworkInterface | None = None):
        # 1. Broadcast packet (255.255.255.255)
        if packet.destination_ip == "255.255.255.255":
            interfaces_to_send = [out_interface] if out_interface else [i for i in self.interfaces if i.status == "up"]
            for intf in interfaces_to_send:
                if intf and intf.link:
                    frame = EthernetFrame(
                        source_mac=intf.mac,
                        destination_mac="FF:FF:FF:FF:FF:FF",
                        payload=packet
                    )
                    intf.send(frame)
            return "BROADCAST_SENT"

        # 2. Local Loopback delivery
        my_ips = [i.ip for i in self.interfaces if i.ip]
        if packet.destination_ip in my_ips or packet.destination_ip == "127.0.0.1":
            in_intf = next((i for i in self.interfaces if i.ip == packet.destination_ip), self.interfaces[0] if self.interfaces else None)
            return self.receive_packet(in_intf, packet)

        # 3. Route lookup
        route = self.lookup_route(packet.destination_ip)
        if not route:
            if out_interface and out_interface.link is not None:
                target_intf = out_interface
                next_hop = packet.destination_ip
            else:
                return "NO_ROUTE"
        else:
            target_intf = route["interface"]
            next_hop = route["next_hop"] or packet.destination_ip

        # 4. ARP Resolution
        dest_mac = self.arp.resolve(next_hop)
        if not dest_mac:
            self.arp.enqueue(next_hop, packet, target_intf)
            self.arp.request(target_intf, next_hop)
            return "ARP_PENDING"

        # 5. Transmit frame
        frame = EthernetFrame(
            source_mac=target_intf.mac,
            destination_mac=dest_mac,
            payload=packet
        )
        return target_intf.send(frame)

    # ========================================================
    # LAYER-2 & LAYER-3 RECEPTION
    # ========================================================

    def receive_frame(self, interface: NetworkInterface, frame: EthernetFrame):
        # Drop if not for our MAC and not broadcast
        if frame.destination_mac != interface.mac and frame.destination_mac != "FF:FF:FF:FF:FF:FF":
            return None

        payload = frame.payload
        if isinstance(payload, ARPPacket):
            return self.arp.receive(interface, payload)
        elif isinstance(payload, Packet):
            return self.receive_packet(interface, payload)
        return None

    def receive_packet(self, interface: NetworkInterface, packet: Packet):
        packet.in_interface = interface
        # Check if local destination
        my_ips = [i.ip for i in self.interfaces if i.ip]
        is_local = (
            packet.destination_ip in my_ips
            or packet.destination_ip in ("255.255.255.255", "127.0.0.1")
        )
        if not is_local and interface.subnet:
            try:
                net = ipaddress.IPv4Network(interface.subnet, strict=False)
                if packet.destination_ip == str(net.broadcast_address):
                    is_local = True
            except Exception:
                pass

        if is_local:
            # Deliver locally
            proto = packet.protocol.upper()
            if proto == "ICMP":
                return self.receive_icmp(interface, packet)
            elif proto == "UDP":
                return self.receive_udp(interface, packet)
            elif proto == "TCP":
                return self.receive_tcp(interface, packet)
            return None

        # Not for us: Forwarding logic (Router)
        if self.forwarding_enabled:
            if packet.ttl <= 1:
                return self.send_icmp_time_exceeded(interface, packet)
            packet.ttl -= 1

            route = self.lookup_route(packet.destination_ip)
            if not route:
                return self.send_icmp_destination_unreachable(interface, packet)

            out_intf = route["interface"]
            if out_intf == interface:
                return "SAME_INTERFACE"

            if self.network:
                self.network.add_event(Event(
                    type="PACKET_FORWARDED",
                    severity="INFO",
                    source=packet.source_ip,
                    destination=packet.destination_ip,
                    protocol=packet.protocol,
                    metadata={
                        "router": self.name,
                        "in_interface": interface.name,
                        "out_interface": out_intf.name
                    }
                ))
            return self.send_ip_packet(packet, out_interface=out_intf)

        return None  # Host drops non-local packet

    # ========================================================
    # ICMP
    # ========================================================

    def receive_icmp(self, interface: NetworkInterface, packet: Packet):
        icmp = packet.payload
        if not isinstance(icmp, ICMPPacket):
            return None

        if icmp.type == "ECHO_REQUEST":
            # Check if this node has an ECHO service: if registered, it must be running to reply
            echo_svc = None
            for s in self.services:
                if s.name.upper() == "ECHO":
                    echo_svc = s
                    break
            if echo_svc is not None and echo_svc.status.lower() != "running":
                # Echo service exists but is stopped -> drop request without reply
                return None

            if getattr(self, "echo_reply_enabled", True) is False:
                return None

            if self.network:
                self.network.add_event(Event(
                    type="ICMP_ECHO_REQUEST_RECEIVED",
                    severity="INFO",
                    source=packet.source_ip,
                    destination=packet.destination_ip,
                    protocol="ICMP"
                ))

            reply_payload = icmp.payload.payload if hasattr(icmp.payload, "payload") else icmp.payload
            reply = ICMPPacket(type="ECHO_REPLY", code=0, payload=reply_payload)
            response = Packet(
                source_ip=packet.destination_ip if packet.destination_ip != "255.255.255.255" else interface.ip,
                destination_ip=packet.source_ip,
                protocol="ICMP",
                payload=reply
            )
            if self.network:
                self.network.add_event(Event(
                    type="ICMP_ECHO_REPLY_SENT",
                    severity="INFO",
                    source=response.source_ip,
                    destination=response.destination_ip,
                    protocol="ICMP"
                ))
            return self.send_ip_packet(response, out_interface=interface)

        elif icmp.type in ("ECHO_REPLY", "TIME_EXCEEDED", "DESTINATION_UNREACHABLE"):
            event_type = f"ICMP_{icmp.type}_RECEIVED"
            if self.network:
                self.network.add_event(Event(
                    type=event_type,
                    severity="INFO" if icmp.type == "ECHO_REPLY" else "WARNING",
                    source=packet.source_ip,
                    destination=packet.destination_ip,
                    protocol="ICMP"
                ))
            self.last_icmp_result = {
                "type": icmp.type,
                "source": packet.source_ip,
                "destination": packet.destination_ip,
                "payload": icmp.payload
            }
            return self.last_icmp_result
        return None

    def send_icmp_time_exceeded(self, in_interface: NetworkInterface, packet: Packet):
        icmp = ICMPPacket(type="TIME_EXCEEDED", code=0, payload=packet)
        response = Packet(
            source_ip=in_interface.ip,
            destination_ip=packet.source_ip,
            protocol="ICMP",
            payload=icmp
        )
        if self.network:
            self.network.add_event(Event(
                type="ICMP_TIME_EXCEEDED_SENT",
                severity="WARNING",
                source=in_interface.ip,
                destination=packet.source_ip,
                protocol="ICMP",
                metadata={"router": self.name, "interface": in_interface.name}
            ))
        return self.send_ip_packet(response)

    def send_icmp_destination_unreachable(self, in_interface: NetworkInterface, packet: Packet, code: int = 0):
        icmp = ICMPPacket(type="DESTINATION_UNREACHABLE", code=code, payload=packet)
        response = Packet(
            source_ip=in_interface.ip,
            destination_ip=packet.source_ip,
            protocol="ICMP",
            payload=icmp
        )
        if self.network:
            self.network.add_event(Event(
                type="ICMP_DESTINATION_UNREACHABLE_SENT",
                severity="HIGH",
                source=in_interface.ip,
                destination=packet.source_ip,
                protocol="ICMP",
                metadata={"router": self.name, "interface": in_interface.name, "code": code}
            ))
        return self.send_ip_packet(response)

    # ========================================================
    # UDP & TCP MULTIPLEXING
    # ========================================================

    def receive_udp(self, interface: NetworkInterface, packet: Packet):
        udp = packet.payload
        if not isinstance(udp, UDPPacket):
            return None

        # 1. Find registered service on this port
        service = None
        for s in self.services:
            if s.port == udp.destination_port:
                if s.protocol.upper() in ("UDP", "TCP/UDP", "ALL") or (s.name.upper() == "ECHO" and s.port == 7):
                    service = s
                    break

        # 2. Check for existing client connection awaiting reply if no service
        if service is None:
            key = (packet.source_ip, udp.source_port, packet.destination_ip, udp.destination_port)
            connection = self.udp_connections.get(key)
            if connection:
                payload = connection.receive(udp)
                connection.last_payload = payload
                self.last_udp_result = {
                    "source": packet.source_ip,
                    "port": udp.source_port,
                    "payload": payload
                }
                return payload

            if packet.destination_ip == "255.255.255.255":
                return None
            if self.network:
                self.network.add_event(Event(
                    type="UDP_PORT_UNREACHABLE",
                    severity="HIGH",
                    source=packet.source_ip,
                    destination=packet.destination_ip,
                    protocol="UDP",
                    port=udp.destination_port,
                    metadata={"host": self.name, "reason": "PORT_CLOSED"}
                ))
            return None

        if service.status.lower() != "running":
            if self.network:
                self.network.add_event(Event(
                    type="UDP_DATAGRAM_DROPPED",
                    severity="HIGH",
                    source=packet.source_ip,
                    destination=packet.destination_ip,
                    protocol="UDP",
                    port=udp.destination_port,
                    metadata={"host": self.name, "reason": "SERVICE_STOPPED"}
                ))
            return None

        # UDP Connection abstraction for event logging
        from backend.network.udp import UDPConnection
        connection = UDPConnection(
            local_ip=packet.destination_ip,
            local_port=udp.destination_port,
            remote_ip=packet.source_ip,
            remote_port=udp.source_port,
            network=self.network
        )

        payload = connection.receive(udp)
        daemon = self.get_service_daemon(service.name)
        app_response = daemon.handle_udp(payload, connection, packet)
        if app_response:
            udp_resp = connection.send(app_response)
            resp_pkt = Packet(
                source_ip=interface.ip,
                destination_ip=packet.source_ip,
                protocol="UDP",
                payload=udp_resp
            )
            self.send_ip_packet(resp_pkt, out_interface=interface)
        return None

    def receive_tcp(self, interface: NetworkInterface, packet: Packet):
        from backend.network.tcp import TCPConnection, TCPState
        tcp_packet = packet.payload
        connection_key = (packet.source_ip, tcp_packet.source_port, packet.destination_ip, tcp_packet.destination_port)
        connection = self.tcp_connections.get(connection_key)

        # 1. Existing client connection handling
        if connection is not None:
            response = connection.receive(tcp_packet)
            if tcp_packet.payload is not None:
                connection.receive_data(tcp_packet)
                connection.last_payload = tcp_packet.payload
                if hasattr(connection, "on_data_received") and callable(connection.on_data_received):
                    connection.on_data_received(tcp_packet.payload)
            if response:
                resp_packet = Packet(
                    source_ip=interface.ip,
                    destination_ip=packet.source_ip,
                    protocol="TCP",
                    payload=response
                )
                self.send_ip_packet(resp_packet, out_interface=interface)
            return None

        # 2. Inbound server connection: find listening service
        service = None
        for s in self.services:
            if s.protocol.upper() == "TCP" and s.port == tcp_packet.destination_port and s.status.lower() == "running":
                service = s
                break
        if service is None:
            if self.network and "RST" not in getattr(tcp_packet, "flags", set()):
                self.network.add_event(Event(
                    type="TCP_PORT_CLOSED",
                    severity="WARNING",
                    source=packet.source_ip,
                    destination=packet.destination_ip,
                    protocol="TCP",
                    port=tcp_packet.destination_port,
                    metadata={"host": self.name, "reason": "PORT_CLOSED"}
                ))
            return None

        if connection is None:
            connection = TCPConnection(
                local_ip=packet.destination_ip,
                local_port=tcp_packet.destination_port,
                remote_ip=packet.source_ip,
                remote_port=tcp_packet.source_port,
                network=self.network
            )
            if tcp_packet.payload is not None:
                connection.state = TCPState.ESTABLISHED
                tcp_packet.flags.add("ACK")
                tcp_packet.sequence_number = connection.acknowledgement_number
            else:
                connection.listen()
            self.tcp_connections[connection_key] = connection

        response = connection.receive(tcp_packet)
        service_data_response = None
        if connection.state.value == "ESTABLISHED" and tcp_packet.payload is not None:
            ack_resp = connection.receive_data(tcp_packet)
            service_name = service.name if 'service' in locals() and service else "UNKNOWN"
            daemon = self.get_service_daemon(service_name)
            app_response = daemon.handle_tcp(tcp_packet.payload, connection, packet)
            if app_response:
                service_data_response = connection.send_data(app_response)

        packets_to_send = []
        if response:
            packets_to_send.append(response)
        if service_data_response:
            packets_to_send.append(service_data_response)
        elif 'ack_resp' in locals() and ack_resp:
            packets_to_send.append(ack_resp)

        for p in packets_to_send:
            resp_packet = Packet(
                source_ip=interface.ip,
                destination_ip=packet.source_ip,
                protocol="TCP",
                payload=p
            )
            self.send_ip_packet(resp_packet, out_interface=interface)

    # ========================================================
    # SERVICE DAEMONS
    # ========================================================

    def add_service(self, service: Service):
        self.services.append(service)

    def remove_service(self, service: Service):
        if service in self.services:
            self.services.remove(service)

    def get_service_daemon(self, service_name: str):
        if service_name not in self.daemons:
            name = service_name.upper()
            if name == "HTTP":
                from backend.services.http import HTTPServerDaemon
                self.daemons[service_name] = HTTPServerDaemon(self)
            elif name in ("SSH", "SSH_SERVER"):
                from backend.services.ssh import SSHServerDaemon
                self.daemons[service_name] = SSHServerDaemon(self)
            elif name == "SSH_CLIENT":
                from backend.services.ssh import SSHClientDaemon
                self.daemons[service_name] = SSHClientDaemon(self)
            elif name in ("DNS", "DNS_SERVER"):
                from backend.services.dns import DNSServerDaemon
                self.daemons[service_name] = DNSServerDaemon(self)
            elif name in ("DHCP", "DHCP_SERVER"):
                from backend.services.dhcp_server import DHCPServerDaemon
                self.daemons[service_name] = DHCPServerDaemon(self)
            elif name == "DHCP_CLIENT":
                from backend.services.dhcp_client import DHCPClientDaemon
                self.daemons[service_name] = DHCPClientDaemon(self)
            elif name == "DHCP_RELAY":
                from backend.services.dhcp_relay import DHCPRelayDaemon
                self.daemons[service_name] = DHCPRelayDaemon(self)
            elif name == "ECHO":
                from backend.services.echo import EchoServerDaemon
                self.daemons[service_name] = EchoServerDaemon(self)
            else:
                from backend.services.base import ServiceDaemon
                self.daemons[service_name] = ServiceDaemon(self)
        return self.daemons[service_name]

    # ========================================================
    # TICK UPDATE
    # ========================================================

    def update(self):
        for interface in self.interfaces:
            interface.process_rx_buffer()
