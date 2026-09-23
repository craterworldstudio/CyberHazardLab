import ipaddress
import random
from .base import ServiceDaemon
from backend.network.packet import UDPPacket, Packet
from backend.network.dhcp_packet import (
    DHCPMessage, DHCPDISCOVER, DHCPOFFER, DHCPREQUEST, DHCPACK, DHCPNAK,
    OPT_MESSAGE_TYPE, OPT_SUBNET_MASK, OPT_ROUTER, OPT_SERVER_ID, OPT_REQUESTED_IP
)
from backend.core.event import Event

class DHCPClientDaemon(ServiceDaemon):
    def on_start(self, service_model):
        """Starts client service: verifies existing IP with DHCPREQUEST, or discovers if unconfigured."""
        if not self.host.interfaces:
            return
        intf = self.host.interfaces[0]

        self.pending_xid = random.randint(100000, 999999)

        if intf.ip and intf.ip not in ("0.0.0.0", ""):
            # INIT-REBOOT state (RFC 2131 Section 3.2 & 4.3.2)
            # Ask server: "Hey! Can I still use this IP?"
            req = DHCPMessage(
                op=1,
                xid=self.pending_xid,
                ciaddr="0.0.0.0",
                chaddr=intf.mac
            )
            req.message_type = DHCPREQUEST
            req.set_option(OPT_REQUESTED_IP, intf.ip)

            udp = UDPPacket(source_port=service_model.port if service_model else 68, destination_port=67, payload=req)
            ip_pkt = Packet(
                source_ip="0.0.0.0",
                destination_ip="255.255.255.255",
                protocol="UDP",
                payload=udp
            )

            if self.host.network:
                self.host.network.add_event(Event(
                    type="DHCP_VERIFY_REQUEST_SENT",
                    severity="INFO",
                    source=self.host.name,
                    destination="BROADCAST",
                    protocol="DHCP",
                    metadata={"mac": intf.mac, "requested_ip": intf.ip, "state": "INIT-REBOOT"}
                ))

            self.host.send_ip_packet(ip_pkt, out_interface=intf)
        else:
            self.send_discover(intf, service_model)

    def send_discover(self, intf, service_model=None):
        self.pending_xid = random.randint(100000, 999999)
        msg = DHCPMessage(
            op=1,
            xid=self.pending_xid,
            chaddr=intf.mac
        )
        msg.message_type = DHCPDISCOVER

        udp = UDPPacket(
            source_port=service_model.port if service_model else 68,
            destination_port=67,
            payload=msg
        )
        ip_pkt = Packet(
            source_ip="0.0.0.0",
            destination_ip="255.255.255.255",
            protocol="UDP",
            payload=udp
        )

        if self.host.network:
            self.host.network.add_event(Event(
                type="DHCP_DISCOVER_SENT",
                severity="INFO",
                source=self.host.name,
                destination="BROADCAST",
                protocol="DHCP",
                metadata={"mac": intf.mac}
            ))

        self.host.send_ip_packet(ip_pkt, out_interface=intf)

    def handle_udp(self, payload, connection, packet):
        if not self.host.interfaces:
            return None
        intf = self.host.interfaces[0]

        # 1. Structured DHCPMessage processing
        if isinstance(payload, DHCPMessage):
            msg = payload
            if msg.chaddr.upper() != intf.mac.upper():
                return None

            if msg.message_type == DHCPOFFER:
                offered_ip = msg.yiaddr
                gateway = msg.get_option(OPT_ROUTER)
                server_id = msg.get_option(OPT_SERVER_ID, packet.source_ip)

                # Send DHCPREQUEST
                req = DHCPMessage(
                    op=1,
                    xid=msg.xid,
                    ciaddr="0.0.0.0",
                    yiaddr=offered_ip,
                    chaddr=intf.mac
                )
                req.message_type = DHCPREQUEST
                req.set_option(OPT_REQUESTED_IP, offered_ip)
                req.set_option(OPT_SERVER_ID, server_id)
                if gateway:
                    req.set_option(OPT_ROUTER, gateway)

                udp = UDPPacket(source_port=68, destination_port=67, payload=req)
                ip_pkt = Packet(
                    source_ip="0.0.0.0",
                    destination_ip="255.255.255.255",
                    protocol="UDP",
                    payload=udp
                )

                if self.host.network:
                    self.host.network.add_event(Event(
                        type="DHCP_REQUEST_SENT",
                        severity="INFO",
                        source=self.host.name,
                        destination="BROADCAST",
                        protocol="DHCP",
                        metadata={"mac": intf.mac, "requested_ip": offered_ip}
                    ))

                self.host.send_ip_packet(ip_pkt, out_interface=intf)
                return None

            elif msg.message_type == DHCPACK:
                assigned_ip = msg.yiaddr
                mask = msg.get_option(OPT_SUBNET_MASK, "255.255.255.0")
                gateway = msg.get_option(OPT_ROUTER)
                
                from backend.network.dhcp_packet import OPT_DNS_SERVER
                dns = msg.get_option(OPT_DNS_SERVER)
                if dns:
                    self.host.dns_server = dns

                # Apply IP & subnet to interface
                net = ipaddress.IPv4Network(f"{assigned_ip}/{mask}", strict=False)
                intf.ip = assigned_ip
                intf.subnet = str(net)
                self.host._install_connected_route(intf)

                # Install default gateway if provided
                if gateway:
                    self.host.add_route("0.0.0.0/0", intf, next_hop=gateway)

                if self.host.network:
                    self.host.network.add_event(Event(
                        type="DHCP_ACK_RECEIVED",
                        severity="INFO",
                        source=packet.source_ip,
                        destination=self.host.name,
                        protocol="DHCP",
                        metadata={"assigned_ip": assigned_ip, "gateway": gateway}
                    ))
                return None

            elif msg.message_type == DHCPNAK:
                # IP rejected / expired -> reset and discover
                if self.host.network:
                    self.host.network.add_event(Event(
                        type="DHCP_NAK_RECEIVED",
                        severity="WARNING",
                        source=packet.source_ip,
                        destination=self.host.name,
                        protocol="DHCP",
                        metadata={"mac": intf.mac, "action": "restart_discover"}
                    ))
                intf.ip = "0.0.0.0"
                intf.subnet = "0.0.0.0/0"
                self.send_discover(intf)
                return None

        # 2. Legacy string fallback support
        payload_str = str(payload).strip().upper()
        if "DHCPOFFER" in payload_str:
            # Parse legacy string format
            parts = payload_str.replace("DHCPOFFER:", "").strip().split()
            offered_ip = None
            gw = None
            for p in parts:
                if p.startswith("IP="): offered_ip = p.split("=")[1]
                elif p.startswith("GW="): gw = p.split("=")[1]
            if offered_ip:
                req = DHCPMessage(op=1, xid=123456, yiaddr=offered_ip, chaddr=intf.mac)
                req.message_type = DHCPREQUEST
                if gw: req.set_option(OPT_ROUTER, gw)
                udp = UDPPacket(source_port=68, destination_port=67, payload=req)
                ip_pkt = Packet(source_ip="0.0.0.0", destination_ip="255.255.255.255", protocol="UDP", payload=udp)
                self.host.send_ip_packet(ip_pkt, out_interface=intf)

        return None
